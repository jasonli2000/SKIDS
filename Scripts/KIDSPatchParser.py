#!/usr/bin/env python
# Parse KIDS files (.KID)
#
#
#---------------------------------------------------------------------------
# Copyright 2011 The Open Source Electronic Health Record Agent
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#---------------------------------------------------------------------------
import sys
import os
import argparse
import re

from LoggerManager import initConsoleLogging, logger
from KIDSPatchInfoParser import installNameToDirName

"""
  KIDS Section Parser Interface
"""
class ISectionParser:
  def __init__(self, **kargs):
    pass
  """
  """
  def onSectionStart(self, section, lines, **kargs):
    pass
  """
  """
  def onSectionEnd(self, section, lines, **kargs):
    pass
  """
  """
  def parseLines(self, section, lines, **kargs):
    pass
  """
  """
  def reset(self, **kargs):
    pass

"""
  Implementation of ISectionParser for debug purpose
"""
class DebugSectionParser(ISectionParser):
  def __init__(self, **kargs):
    self.__logKargs__(**kargs)
  def onSectionStart(self, section, lines, **kargs):
    self.__logFunctionCallInfo__("onSectionStart", section, lines, **kargs)
  def onSectionEnd(self, section, lines, **kargs):
    self.__logFunctionCallInfo__("onSectionEnd", section, lines, **kargs)
  def parseLines(self, section, lines, **kargs):
    self.__logFunctionCallInfo__("parseLines", section, lines, **kargs)
  def reset(self, **kargs):
    logger.debug("Function reset is called")
    self.__logKargs__(**kargs)
  def __logKargs__(self, **kargs):
    for (key, value) in kargs.iteritems():
      logger.debug("Key: %s, Val: %s" % (key, value))

  def __logFunctionCallInfo__(self, funcName, section, lines, **kargs):
    logger.debug("Function %s is called" % funcName)
    logger.debug("Current Section is: %s" % section)
    if lines:
      for line in lines:
        logger.debug("line: [%s]" % line)
    self.__logKargs__(**kargs)

"""
  KIDS Routine Section Parser
  @inherits ISectionParser
"""
class RoutineSectionParser(ISectionParser):
  ROUTINE_START = re.compile("^\"RTN\"\)")
  NEW_ROUTINE_START = re.compile("^\"RTN\",\"(?P<Name>[^,\"]+)\"\)$")
  """
  """
  def __init__(self, outputDir, **kargs):
    self._outDir = outputDir
    self._fileHandler = None
    self.reset(**kargs)
  """
    Implement ISectionParser interface
  """
  """
    @override ISectionParser::onSectionStart
  """
  def onSectionStart(self, section, lines, **kargs):
    assert ('kidsBuild' in kargs and kargs['kidsBuild'] != None)
    kidsBuild = kargs['kidsBuild']
    logger.debug("Routine Section starts %s, %s" % (lines[0], lines[1]))
    if self.ROUTINE_START.search(lines[0]):
      kidsBuild._totalNumRoutinesChange = int(lines[1])
    else:
      logger.error("Unexpected Routine Section [%s]" % lines)
      return False
    return True
  """
    @override ISectionParser::onSectionEnd
  """
  def onSectionEnd(self, section, lines, **kargs):
    assert ('kidsBuild' in kargs and kargs['kidsBuild'] != None)
    kidsBuild = kargs['kidsBuild']
    logger.debug("Routine Section Ends %s, %s" % (lines[0], lines[1]))
    self.__onCurrentRoutineEnd__(kidsBuild)
    self.reset(**kargs)
  """
    @override ISectionParser::parseLines
  """
  def parseLines(self, section, lines, **kargs):
    assert ('kidsBuild' in kargs and kargs['kidsBuild'] != None)
    kidsBuild = kargs['kidsBuild']
    logger.debug("Parsing Routine Line %s, %s" % (lines[0], lines[1]))
    result = self.NEW_ROUTINE_START.search(lines[0])
    if result:
      return self.__onNewRoutineStart__(section, lines, result, kidsBuild)
    else:
      return self.__parseRoutineLines__(section, lines, result)
  """
    @override ISectionParser::reset
  """
  def reset(self, **kargs):
    self._curRoutine = None
    self._checkSum = 0
    if self._fileHandler:
      self._fileHandler.close()
    self._fileHandler = None
  """
    Private Implementation
  """
  """
  """
  def __onCurrentRoutineEnd__(self, kidsBuild):
    if self._curRoutine:
      self._curRoutine.checkSum = self._checkSum
      if self._curRoutine.expectCheckSum != self._checkSum:
        logger.error("%s checksum mispatch, expected %s, real: %s" %
                      (self._curRoutine.name, self._curRoutine.expectCheckSum,
                       self._checkSum))
      self._checkSum = 0
      kidsBuild.addRoutine(self._curRoutine)
    if self._fileHandler:
      self._fileHandler.close()
  """
  """
  def __onNewRoutineStart__(self, section, lines, result, kidsBuild):
    routineName = result.group('Name')
    assert (self._curRoutine == None or
            self._curRoutine.name != routineName)
    if self._curRoutine:
      self.__onCurrentRoutineEnd__(kidsBuild)
    self._curRoutine = Routine()
    self._curRoutine.name = routineName
    # format is unknown^unknown^AfterCheckSum^BeforeCheckSum
    propInfo = lines[1].split('^')
    assert len(propInfo) > 1
    flag = int(propInfo[0])
    self._curRoutine.flag = flag
    if flag == 1: # need to be deleted
      self._curRoutine.expectCheckSum = 0
      return

    patchDir = installNameToDirName(kidsBuild.installName)
    destDir = os.path.join(self._outDir, patchDir)
    if not os.path.exists(destDir):
      os.mkdir(destDir)
    routineDest = os.path.join(destDir, "%s.m" % routineName)
    self._fileHandler = open(routineDest, 'w') # open for write
    if len(propInfo) > 2:
      try:
        self._curRoutine.expectCheckSum = int(propInfo[2][1:])
      except ValueError as err:
        logger.error(err)
        logger.error("Invalid Routine Line %s, %s" % (lines[0], lines[1]))
        self._curRoutine.expectCheckSum = 0
    else:
      logger.error("Invalid Routine Line %s, %s" % (lines[0], lines[1]))
      self._curRoutine.expectCheckSum = 0
  """
    Parse source code of the routine
  """
  def __parseRoutineLines__(self, section, lines, result):
    assert self._curRoutine
    routineLine, sourceLine = lines
    assert routineLine.endswith(",0)")
    assert routineLine.find("\"RTN\",\"%s\"," % self._curRoutine.name) == 0
    lineNum = int(routineLine.split(',')[2])
    if self._curRoutine.sourceCode == None:
      self._curRoutine.sourceCode = []
    #self._curRoutine.sourceCode.append(sourceLine)
    self._curRoutine.sourceCode.append("")
    self._fileHandler.write("%s\n" % sourceLine)
    assert lineNum == len(self._curRoutine.sourceCode)
    """ calculate checksum """
    if lineNum == 2: # ignore line # 2
      return
    self._checkSum += routineLineCheckSum(sourceLine, lineNum)

"""
  KIDS Build Section Parser
  @inherits ISectionParser
"""
class BuildSectionParser(ISectionParser):
  def __init__(self, **kargs):
    self.reset(**kargs)
    self.__initHandler__()
  """
  """
  def onSectionStart(self, section, lines, **kargs):
    buildNode = lines[0].split(',')[1]
    if self._curBuildNode:
      assert self._curBuildNode == buildNode
    else:
      self._curBuildNode = buildNode
    self.parseLines(section, lines, **kargs)
  """
  """
  def onSectionEnd(self, section, lines, **kargs):
    self.reset(**kargs)
  """
  """
  def parseLines(self, section, lines, **kargs):
    kidsBuild = kargs['kidsBuild']
    for (regEx, handler) in self._handlers:
      if regEx.search(lines[0]):
        handler(lines, kidsBuild)
        return
  """
    @override ISectionParser::reset
  """
  def reset(self, **kargs):
    self._curBuildNode = None
  """
    private implementation
  """
  def __initHandler__(self):
    """ based on BUILD file schema """
    self._handlers = (
      (re.compile(',"INI"\)$'), self.__handlePreInstallRoutine__),
      (re.compile(',"INIT"\)$'), self.__handlePostInstallRoutine__),
      (re.compile(',"PRE"\)$'), self.__handleEnvCheckRoutine__),
      (re.compile(',6\)$'), self.__handleSeqNo__),
      (re.compile(',"INID"\)$'), self.__handleRoutineCleanup__)
    )
  def __handlePreInstallRoutine__(self, lines, kidsBuild):
    line2 = lines[1]
    preInstallRoutine = line2.strip(' ')
    if kidsBuild.preInstallRoutine:
      assert kidsBuild.preInstallRoutine == preInstallRoutine
    else:
      kidsBuild.preInstallRoutine = preInstallRoutine
  def __handlePostInstallRoutine__(self, lines, kidsBuild):
    line2 = lines[1]
    postInstallRoutine = line2.strip(' ')
    if kidsBuild.postInstallRoutine:
      assert kidsBuild.postInstallRoutine == postInstallRoutine
    else:
      kidsBuild.postInstallRoutine = postInstallRoutine
  def __handleEnvCheckRoutine__(self, lines, kidsBuild):
    line2 = lines[1]
    envCheckRoutine = line2.strip(' ')
    if kidsBuild.envCheckRoutine:
      assert kidsBuild.envCheckRoutine == envCheckRoutine
    else:
      kidsBuild.envCheckRoutine = envCheckRoutine
  def __handleSeqNo__(self, lines, kidsBuild):
    line1, line2 = lines
    if len(line1.split(',')) == 3:
      seqNo = line2.strip(' ').split('^')[-1]
      if len(seqNo):
        kidsBuild.seqNo = int(seqNo)
  def __handleRoutineCleanup__(self, lines, kidsBuild):
    line2 = lines[1]
    options = line2.split('^')
    if len(options) >= 1 and options[0] == 'y':
      kidsBuild.deleteEnvCheckRoutine = True
    if len(options) >=2 and options[1] == 'y':
      kidsBuild.deletePostInstallRoutine = True
    if len(options) ==3 and options[2] == 'y':
      kidsBuild.deletePreInstallRoutine = True
"""
  object to store information related to a KIDS build
"""
class KIDSBuild(object):
  def __init__(self, installName):
    self._installName = installName
    self._verName = None
    """ Routine sections """
    self._routineList = None
    self._totalNumRoutinesChange = None
    self._preInstallRoutine = None
    self._postInstallRoutine = None
    self.envCheckRoutine = None
    self.deletePreInstallRoutine = False
    self.deletePostInstallRoutine = False
    self.deleteEnvCheckRoutine = False
    self.seqNo = None

  def addRoutine(self, Routine):
    if not self._routineList:
      self._routineList = []
    self._routineList.append(Routine)

  """ installName property """
  @property
  def installName(self):
    """ installName property read only """
    return self._installName
  """ preInstallRoutine property """
  @property
  def preInstallRoutine(self):
    return self._preInstallRoutine
  @preInstallRoutine.setter
  def preInstallRoutine(self, preInstallRoutine):
    self._preInstallRoutine = preInstallRoutine
  """ postInstallRoutine property """
  @property
  def postInstallRoutine(self):
    return self._postInstallRoutine
  @postInstallRoutine.setter
  def postInstallRoutine(self, RoutineName):
    self._postInstallRoutine = RoutineName
  @property
  def routineList(self):
    return self._routineList

  def __repr__(self):
    return ("%s, seq:%s, ver:%s, pre:%s, env:%s, post:%s, "
            "delEnv:%s, delPost:%s, delPre:%s, totalRoutine Affected:%s,\n%s" %
             ( self._installName, self.seqNo, self._verName,
               self._preInstallRoutine, self.envCheckRoutine,
               self._postInstallRoutine, self.deleteEnvCheckRoutine,
               self.deletePostInstallRoutine, self.deletePreInstallRoutine,
               self._totalNumRoutinesChange, self._routineList
             )
           )
"""
  Object to store routine information
"""
class Routine(object):
  """ enums & constants"""
  INSTALL = 0
  DELETE = 1

  """ mapping dictionary """
  ROUTINE_FLAG_DICT = {
      INSTALL : "Install",
      DELETE : "Delete"
  }

  def __init__(self):
    self.name = None
    self.sourceCode = None
    self.checkSum = None
    self.expectCheckSum = None
    self.flag = None # modified, delete, post/pre-install

  @staticmethod
  def getRoutineFlag(flag):
    return Routine.ROUTINE_FLAG_DICT.get(flag, "")

  def __repr__(self):
    return ( "(Name:%s, checksum:%s, expected checksum:%s, flag:%s)\n" %
             ( self.name, self.checkSum, self.expectCheckSum,
               self.getRoutineFlag(self.flag)
             )
           )
"""
  class to parse KIDS Build, also implement ISectionParser Interface for install Name
"""
class KIDSPatchParser(object, ISectionParser):
  """
    enum for section
  """
  KIDS_PATCH_SECTION = 0
  INSTALL_NAME_SECTION = 1
  DATA_SECTION = 2
  DD_SECTION = 3
  SEC_SECTION = 4
  UP_SECTION = 5
  QUES_SECTION = 6
  TEMP_SECTION = 7
  MBREQ_SECTION = 8
  ORD_SECTION = 9
  ROUTINE_SECTION = 10
  BUILD_SECTION = 11
  VERSION_SECTION = 12
  PRE_INSTALL_SECTION = 13 # pre-install routine
  POST_INSTALL_SECTION = 14
  KRN_SECTION = 15
  PKG_SECTION = 16
  END_SECTION = 17
  DIC_SECTION = 18
  PRE_SECTION = 19 # env check routine
  FIA_SECTION = 20
  IX_SECTION = 21
  KEY_SECTION = 22
  KEYPTR_SECTION = 23
  PGL_SECTION = 24
  FRV1_SECTION = 25
  FRV1K_SECTION = 26

  """
    regular expression to determine the start of the section
  """
  BUILD_START = re.compile("^\"BLD\",[0-9]+,0\)$")
  VER_START = re.compile("^\"VER\"\)")
  """
    regular expression to determine which section that current line belongs to
  """
  KIDS_PATCH_LINE = re.compile("^\*\*KIDS\*\*")
  INSTALL_NAME_LINE = re.compile("^\*\*INSTALL NAME\*\*$")
  DATA_LINE = re.compile("^\"DATA\"")
  DATA_DICTIONARY_LINE = re.compile("^\"\^DD\",")
  SEC_LINE = re.compile("^\"SEC\",")
  UP_LINE = re.compile("^\"UP\",")
  QUES_LINE = re.compile("^\"QUES\",\".*\",.*\)$")
  TEMP_LINE = re.compile("^\"TEMP\",")
  MBREQ_LINE = re.compile("\"MBREQ\"")
  ORD_LINE = re.compile("^\"ORD\",") # option, RPC, templates etc
  ROUTINE_LINE = re.compile("^\"RTN\"")
  BUILD_LINE = re.compile("^\"BLD\",[0-9]+")
  VERSION_LINE = re.compile("^\"VER\"\)$")
  PRE_INSTALL_ROUTINE_LINE = re.compile("^\"INI\"\)$")
  POST_INSTALL_ROUTINE_LINE = re.compile("^\"INIT\"\)$")
  KRN_LINE = re.compile("^\"KRN\",")
  PKG_LINE = re.compile("^\"PKG\",")
  END_LINE = re.compile("^\*\*END\*\*$")
  DIC_LINE = re.compile("^\"\^DIC\"")
  PRE_LINE = re.compile("^\"PRE\"\)$")
  FIA_LINE = re.compile("^\"FIA\"")
  IX_LINE = re.compile("^\"IX\"")
  KEY_LINE = re.compile("^\"KEY\"")
  KEYPTR_LINE = re.compile("^\"KEYPTR\"")
  PGL_LINE = re.compile("^\"PGL\"")
  FRV1_LINE = re.compile("^\"FRV1\"")
  FRV1K_LINE = re.compile("^\"FRV1K\"")

  def __init__(self, outDir):
    assert os.path.exists(outDir)
    self._outDir = outDir
    self._kidsBuilds = []
    self._curKidsBuild = None
    self._curParser = None
    self._curSection = None
    self._outDir = None
    self._regExSectionMapping = dict()
    self._sectionHandler = None
    self.__initSectionLineRegEx__(outDir)
    self.__initSectionHandler__()
  """
    main workflow to parse a KIDS build
    @kidsPatch: file path of a KIDS file
  """
  def parseKIDSBuild(self, kidsPatch):
    assert os.path.exists(kidsPatch)
    logger.info("Parsing KIDS file %s" % kidsPatch)
    lines = None
    with open(kidsPatch, 'r') as input:
      curLine = input.readline()
      lineNum = 0
      while len(curLine) > 0:
        lineNum += 1
        """ read one more line """
        lines = (curLine.rstrip('\r\n'), input.readline().rstrip('\r\n'))
        if lineNum == 1:
          self.__parseKIDSHeader__(lines)
        else:
          section, parser = self.__isSectionLine__(curLine)
          if section == None: # could not find a valid section
            logger.warn("Can not parse %s" % lines[0])
            self.__resetCurrentSection__(section, parser, lines)
          else: # find a section
            if section != self._curSection:
              self.__resetCurrentSection__(section, parser, lines)
            elif self._curParser:
              self._curParser.parseLines(section, lines,
                                         kidsBuild=self._curKidsBuild)
        # goto the next line #
        lineNum += 1
        curLine = input.readline()
      else: # at end of file
        self.__resetCurrentSection__(None, None, lines)

  """
    print the result
  """
  def printResult(self):
    for kidsBuild in self._kidsBuilds:
      print kidsBuild
      if kidsBuild.preInstallRoutine:
        preRtn = kidsBuild.preInstallRoutine.split('^')[-1]
        assert preRtn in [x.name for x in kidsBuild.routineList]
      if kidsBuild.postInstallRoutine:
        postRtn = kidsBuild.postInstallRoutine.split('^')[-1]
        assert postRtn in [x.name for x in kidsBuild.routineList]
      if kidsBuild.envCheckRoutine:
        envRtn = kidsBuild.envCheckRoutine.split('^')[-1]
        assert envRtn in [x.name for x in kidsBuild.routineList]
  def printRoutineResult(self):
    pass

  """
    reset the current section and corresponding parser
    invoke previous section's handler if applicable
  """
  def __resetCurrentSection__(self, section, parser, lines):
    if self._curSection:
      if self._curParser:
        self._curParser.onSectionEnd(self._curSection, lines,
                                     kidsBuild=self._curKidsBuild)
    self._curSection = section
    self._curParser = parser
    if section and parser:
      parser.onSectionStart(section, lines, kidsBuild=self._curKidsBuild)
  """ Initial the LineRegEx -> (section, parser) mapping """
  def __initSectionLineRegEx__(self, outDir):
    """ mapping line regex with section and corresponding section parser """
    debugParser = DebugSectionParser()
    routineParser = RoutineSectionParser(outDir)
    self._regExSectionMapping = {
      self.KIDS_PATCH_LINE : (self.KIDS_PATCH_SECTION, self),
      self.INSTALL_NAME_LINE : (self.INSTALL_NAME_SECTION, self),
      self.DATA_LINE : (self.DATA_SECTION, debugParser),
      self.DATA_DICTIONARY_LINE : (self.DD_SECTION, debugParser),
      self.SEC_LINE : (self.SEC_SECTION, debugParser),
      self.UP_LINE : (self.UP_SECTION, debugParser),
      self.QUES_LINE : (self.QUES_SECTION, debugParser),
      self.TEMP_LINE : (self.TEMP_SECTION, debugParser),
      self.MBREQ_LINE : (self.MBREQ_SECTION, debugParser),
      self.ORD_LINE : (self.ORD_SECTION, debugParser),
      self.ROUTINE_LINE : (self.ROUTINE_SECTION, routineParser),
      self.BUILD_LINE : (self.BUILD_SECTION, BuildSectionParser()),
      self.PRE_INSTALL_ROUTINE_LINE : (self.PRE_INSTALL_SECTION, self),
      self.POST_INSTALL_ROUTINE_LINE : (self.POST_INSTALL_SECTION, self),
      self.KRN_LINE: (self.KRN_SECTION, None),
      self.PKG_LINE: (self.PKG_SECTION, self),
      self.END_LINE: (self.END_SECTION, self),
      self.DIC_LINE: (self.DIC_SECTION, None),
      self.PRE_LINE: (self.PRE_SECTION, self),
      self.FIA_LINE: (self.FIA_SECTION, None),
      self.IX_LINE: (self.IX_SECTION, None),
      self.KEY_LINE: (self.KEY_SECTION, None),
      self.KEYPTR_LINE: (self.KEYPTR_SECTION, None),
      self.PGL_LINE: (self.PGL_SECTION, None),
      self.FRV1_LINE: (self.FRV1_SECTION, None),
      self.FRV1K_LINE: (self.FRV1K_SECTION, None),
      self.VERSION_LINE : (self.VERSION_SECTION, self)
    }

  """
    Method to check if current line is a valid section line
    @return (None, None) if not valid, else return (section, parser)
  """
  def __isSectionLine__(self, curLine):
    for regex in self._regExSectionMapping.iterkeys():
      if regex.search(curLine):
        return self._regExSectionMapping[regex]
    return (None, None)

  """
    Implementation of INSTALL_NAME_SECTION and KIDS_PATCH_SECTION parser
  """
  """
  @override ISectionParser::onSectionStart
  """
  def onSectionStart(self, section, lines, **kargs):
    handler = self._sectionHandler.get(section, None)
    if handler:
      handler(section, lines, **kargs)
  def __onPreInstallSectionStart__(self, section, lines, **kargs):
    line2 = lines[1]
    preInstallRoutine = line2.strip(' ')
    kidsBuild = self._curKidsBuild
    assert kidsBuild
    if kidsBuild.preInstallRoutine:
      assert kidsBuild.preInstallRoutine == preInstallRoutine
    else:
      kidsBuild.preInstallRoutine = preInstallRoutine
  def __onPostInstallSectionStart__(self, section, lines, **kargs):
    line2 = lines[1]
    postInstallRoutine = line2.strip(' ')
    kidsBuild = self._curKidsBuild
    assert kidsBuild
    if kidsBuild.postInstallRoutine:
      assert kidsBuild.postInstallRoutine == postInstallRoutine
    else:
      kidsBuild.postInstallRoutine = postInstallRoutine
  def __onEnvCheckSectionStart__(self, section, lines, **kargs):
    line2 = lines[1]
    envCheckRoutine = line2.strip(' ')
    kidsBuild = self._curKidsBuild
    assert kidsBuild
    if kidsBuild.envCheckRoutine:
      assert kidsBuild.envCheckRoutine == envCheckRoutine
    else:
      kidsBuild.envCheckRoutine = envCheckRoutine
  def __onInstallNameSectionStart__(self, section, lines, **kargs):
    installName = lines[1].strip(' ') # just in case
    if self._curKidsBuild:
      assert self._curKidsBuild.installName != installName
    self._curKidsBuild = KIDSBuild(installName)
    self._kidsBuilds.append(self._curKidsBuild)
  def __onKidsPatchSectionStart__(self, section, lines, **kargs):
    pass
  def __onEndSectionStart__(self, section, lines, **kargs):
    pass
  def __onVersionSecionStart__(self, section, lines, **kargs):
    pass
  def __initSectionHandler__(self):
    self._sectionHandler = {
        self.KIDS_PATCH_SECTION: self.__onKidsPatchSectionStart__,
        self.PRE_INSTALL_SECTION: self.__onPreInstallSectionStart__,
        self.POST_INSTALL_SECTION: self.__onPostInstallSectionStart__,
        self.PRE_SECTION: self.__onEnvCheckSectionStart__,
        self.END_SECTION: self.__onEndSectionStart__,
        self.VERSION_SECTION: self.__onVersionSecionStart__,
        self.INSTALL_NAME_SECTION: self.__onInstallNameSectionStart__
    }
  def __parseKIDSHeader__(self, lines):
    pass

def routineLineCheckSum(routineLine, lineNum):
  totalLen = len(routineLine)
  pos = routineLine.find(' ')
  if pos < 0:
    logger.error("no space in the line %s at %s, return 0" %
                 (routineLine, lineNum))
    return 0
    #raise Exception("Invalid Routine source code")
  if (totalLen > pos+1 and routineLine[pos+1] == ';'):
    if (totalLen <= pos+2 or routineLine[pos+2] != ';'):
      # trancate the string only if the it is ; not ;;
      totalLen = pos
  checkSum = 0
  for i in xrange(totalLen):
    checkSum += (lineNum+i+1)*ord(routineLine[i])
  return checkSum

def checksum(routine):
  checksum = 0
  lineNumber = 0
  with open(routine, 'r') as f:
    for line in f:
      line = line.rstrip('\r\n')
      lineNumber += 1
      # ignore the second line
      if lineNumber == 2:
        continue
      checksum += routineLineCheckSum(line, lineNumber)
  return checksum

def main():
  parser = argparse.ArgumentParser(description='VistA KIDS Patch Parser')
  parser.add_argument('-i', '--inputKIDSPatch', required=True,
                      help = 'Input KIDS Patch file')
  parser.add_argument('-o', '--outputDir', required=True,
                      help = 'Output directory to store extracted M routines')
  parser.add_argument('-c', '--checksum', default=False, action="store_true",
                      help = 'Print checksum of a M Routine')
  result = parser.parse_args();
  import logging
  initConsoleLogging(logging.INFO)
  if result.checksum:
    chksum= checksum(result.inputKIDSPatch)
    sys.stdout.write("Checksum is: %s\n" % chksum)
  else:
    kidsParser = KIDSPatchParser(result.outputDir)
    kidsParser.parseKIDSBuild(result.inputKIDSPatch)
    kidsParser.printResult()
    #unpack(result.inputKIDSPatch, result.outputDir)

if __name__ == '__main__':
    main()
