import json
import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging

#
# action classes
#
class AnimatorAction(object):
  """Superclass for actions to be animated."""
  def __init__(self):
    self.name = "Action"
    self.startTime = 0 # in seconds from start of script
    self.endTime = 0

class TranslationAction(AnimatorAction):
  """Defines an animation of a transform"""
  def __init__(self):
    super(TranslationAction,self).__init__()
    self.name = "TranslationAction"

  def react(self, action, scriptTime):
    startTransform = slicer.mrmlScene.GetNodeByID(action['startTransformID'])
    endTransform = slicer.mrmlScene.GetNodeByID(action['endTransformID'])
    proxyTransform = slicer.mrmlScene.GetNodeByID(action['proxyTransformID'])
    if scriptTime <= action['startTime']:
      matrix = vtk.vtkMatrix4x4()
      startTransform.GetMatrixTransformFromParent(matrix)
      proxyTransform.SetMatrixTransformFromParent(matrix)
    elif scriptTime >= action['endTime']:
      matrix = vtk.vtkMatrix4x4()
      endTransform.GetMatrixTransformFromParent(matrix)
      proxyTransform.SetMatrixTransformFromParent(matrix)
    else:
      actionTime = scriptTime - action['startTime']
      duration = action['endTime'] - action['startTime']
      fraction = actionTime / duration
      startMatrix = vtk.vtkMatrix4x4()
      startTransform.GetMatrixTransformFromParent(startMatrix)
      endMatrix = vtk.vtkMatrix4x4()
      endTransform.GetMatrixTransformFromParent(endMatrix)
      proxyMatrix = vtk.vtkMatrix4x4()
      proxyMatrix.DeepCopy(startMatrix)
      for i in range(3):
        start = startMatrix.GetElement(i,3)
        end = endMatrix.GetElement(i,3)
        delta = fraction * (end-start)
        # TODO: add interpolation and ease in/out options
        proxyMatrix.SetElement(i,3, start + delta)
      proxyTransform.SetMatrixTransformFromParent(proxyMatrix)

# add an module-specific dict for any module other to add animator plugins.
# these must be subclasses (or duck types) of the
# AnimatorAction class below.  Dict keys are action types
# and values are classes
try:
  slicer.modules.animatorActionPlugins
except AttributeError:
  slicer.modules.animatorActionPlugins = {}
slicer.modules.animatorActionPlugins['TranslationAction'] = TranslationAction


#
# Animator
#

class Animator(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Animator" # TODO make this more human readable by adding spaces
    self.parent.categories = ["Wizards"]
    self.parent.dependencies = []
    self.parent.contributors = ["Steve Pieper (Isomics, Inc.)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
A high-level animation interface that operates on top of the Sequences and Screen Capture interfaces.
"""
    self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc.
and Steve Pieper, Isomics, Inc. and was partially funded by NIH grant 3P41RR013218-12S1.
""" # replace with organization, grant and thanks.


#
# AnimatorWidget
#

class AnimatorWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """


  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    # tracks the modified event observer on the currently
    # selected sequence browser node
    self.sequenceBrowserObserverRecord = None

    self.logic = AnimatorLogic()

    # Instantiate and connect widgets ...

    #
    # Parameters Area
    #
    parametersCollapsibleButton = ctk.ctkCollapsibleButton()
    parametersCollapsibleButton.text = "Animation Parameters"
    self.layout.addWidget(parametersCollapsibleButton)

    # Layout within the dummy collapsible button
    parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)

    #
    # input volume selector
    #
    self.animationSelector = slicer.qMRMLNodeComboBox()
    self.animationSelector.nodeTypes = ["vtkMRMLScriptedModuleNode"]
    self.animationSelector.selectNodeUponCreation = True
    self.animationSelector.addEnabled = True
    self.animationSelector.addAttribute("vtkMRMLScriptedModuleNode", "ModuleName", "Animation")
    self.animationSelector.baseName = "Animation"
    self.animationSelector.removeEnabled = True
    self.animationSelector.noneEnabled = True
    self.animationSelector.showHidden = True
    self.animationSelector.showChildNodeTypes = False
    self.animationSelector.setMRMLScene( slicer.mrmlScene )
    self.animationSelector.setToolTip( "Pick the animation description." )
    parametersFormLayout.addRow("Animation Node: ", self.animationSelector)

    self.sequencePlay = slicer.qMRMLSequenceBrowserPlayWidget()
    self.sequencePlay.setMRMLScene(slicer.mrmlScene)
    self.sequenceSeek = slicer.qMRMLSequenceBrowserSeekWidget()
    self.sequenceSeek.setMRMLScene(slicer.mrmlScene)

    parametersFormLayout.addRow(self.sequencePlay)
    parametersFormLayout.addRow(self.sequenceSeek)

    # connections
    self.animationSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)

    # Add vertical spacer
    self.layout.addStretch(1)

  def cleanup(self):
    pass

  def onSelect(self):
    sequenceBrowserNode = None
    sequenceNode = None
    animationNode = self.animationSelector.currentNode()
    if animationNode:
      sequenceBrowserNodeID = animationNode.GetAttribute('Animator.sequenceBrowserNodeID')
      sequenceBrowserNode = slicer.mrmlScene.GetNodeByID(sequenceBrowserNodeID)
      sequenceNodeID = animationNode.GetAttribute('Animator.sequenceNodeID')
      sequenceNode = slicer.mrmlScene.GetNodeByID(sequenceNodeID)
      if self.sequenceBrowserObserverRecord:
        object,tag = self.sequenceBrowserObserverRecord
        object.RemoveObserver(tag)

      def onBrowserModified(caller, event):
        index = sequenceBrowserNode.GetSelectedItemNumber()
        scriptTime = float(sequenceNode.GetNthIndexValue(index))
        self.logic.react(animationNode, scriptTime)
      tag = sequenceBrowserNode.AddObserver(vtk.vtkCommand.ModifiedEvent, onBrowserModified)
      self.sequenceBrowserObserverRecord = (sequenceBrowserNode, tag)

    self.sequencePlay.setMRMLSequenceBrowserNode(sequenceBrowserNode)
    self.sequenceSeek.setMRMLSequenceBrowserNode(sequenceBrowserNode)




#
# AnimatorLogic
#

class AnimatorLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def getScript(self, animationNode):
    scriptJSON = animationNode.GetAttribute("Animation.script") or "{}"
    script = json.loads(scriptJSON)
    return(script)

  def setScript(self, animationNode, script):
    scriptJSON = json.dumps(script)
    animationNode.SetAttribute("Animation.script", scriptJSON)

  def getActions(self, animationNode):
    script = self.getScript(animationNode)
    actions = script['actions'] if hasattr(script, "actions") else []
    return(actions)

  def addAction(self, animationNode, action):
    """Add an action to the script """
    script = self.getScript(animationNode)
    actions = self.getActions(animationNode)
    actions.append(action)
    script['actions'] = actions
    self.setScript(animationNode, script)

  def compileScript(self, animationNode, sequenceBrowserNode=None):
    """Convert the node's script into sequences and a sequence browser node.
       TODO: Replace the passed sequenceBrowserNode if given.
       Returns the sequenceBrowserNode.
    """
    sequenceBrowserNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLSequenceBrowserNode')
    sequenceBrowserNode.SetName(animationNode.GetName() + "-Browser")

    sequenceNodes = {}
    script = self.getScript(animationNode)
    actions = script['actions']
    endTime = 0
    for action in actions:
      endTime = max(endTime, action['endTime'])

    sequenceNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLSequenceNode')
    sequenceNode.SetIndexType(sequenceNode.NumericIndex)
    sequenceNode.SetName(animationNode.GetName() + "-TimingSequence")
    sequenceBrowserNode.AddSynchronizedSequenceNode(sequenceNode)

    steps = script['fps'] * endTime
    for step in range(steps):
      scriptTime = 1. * step / steps
      timePointDataNode = slicer.vtkMRMLScriptedModuleNode()
      sequenceNode.SetDataNodeAtValue(timePointDataNode, str(scriptTime))

    return(sequenceBrowserNode)


  def react(self, animationNode, scriptTime):
    """Give each action in the script a chance to react to the current script time"""
    script = self.getScript(animationNode)
    actions = script['actions']
    for action in actions:
      actionInstance = slicer.modules.animatorActionPlugins[action['class']]()
      actionInstance.react(action, scriptTime)



class AnimatorTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_Animator1()

  def test_Animator1(self):
    """ Ideally you should have several levels of tests.  At the lowest level
    tests should exercise the functionality of the logic with different inputs
    (both valid and invalid).  At higher levels your tests should emulate the
    way the user would interact with your code and confirm that it still works
    the way you intended.
    One of the most important features of the tests is that it should alert other
    developers when their changes will have an impact on the behavior of your
    module.  For example, if a developer removes a feature that you depend on,
    your test should break so they know that the feature is needed.
    """

    self.delayDisplay("Starting the test", 10)
    #
    # first, get some data
    #
    import SampleData
    mrHead = SampleData.downloadSample('MRHead')
    slicer.util.delayDisplay("Head downloaded...",1)

    animationNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLScriptedModuleNode')
    animationNode.SetName('SelfTest Animation')
    animationNode.SetAttribute('ModuleName', 'Animation')

    logic = AnimatorLogic()

    script = {}
    script['title'] = "SelfTest Script"
    script['duration'] = 5 # in seconds
    script['fps'] = 30
    logic.setScript(animationNode, script)

    startTransform = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode')
    startTransform.SetName('Start Transform')
    endTransform = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode')
    endTransform.SetName('End Transform')
    proxyTransform = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode')
    proxyTransform.SetName('Proxy Transform')

    matrix = vtk.vtkMatrix4x4()
    matrix.SetElement(0,3, 10)
    matrix.SetElement(1,3, 5)
    matrix.SetElement(2,3, 15)
    endTransform.SetMatrixTransformFromParent(matrix)

    mrHead.SetAndObserveTransformNodeID(proxyTransform.GetID())

    action = {
      'name': 'SelfTest Translation',
      'class': 'TranslationAction',
      'id': 'transform1',
      'startTime': 0,
      'endTime': 3,
      'interpolation': 'linear',
      'startTransformID': startTransform.GetID(),
      'endTransformID': endTransform.GetID(),
      'proxyTransformID': proxyTransform.GetID(),
    }

    logic.addAction(animationNode, action)

    sequenceBrowserNode = logic.compileScript(animationNode)

    sequenceNodes = vtk.vtkCollection()
    sequenceBrowserNode.GetSynchronizedSequenceNodes(sequenceNodes, True) # include master
    sequenceNode = sequenceNodes.GetItemAsObject(0)

    animationNode.SetAttribute('Animator.sequenceBrowserNodeID', sequenceBrowserNode.GetID())
    animationNode.SetAttribute('Animator.sequenceNodeID', sequenceNode.GetID())

    slicer.modules.AnimatorWidget.animationSelector.setCurrentNode(animationNode)

    sequenceBrowserNode.SetPlaybackActive(True)

    self.delayDisplay('Test passed!')
