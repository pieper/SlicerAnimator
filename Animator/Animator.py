import json
import math
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
    targetTransform = slicer.mrmlScene.GetNodeByID(action['targetTransformID'])
    if scriptTime <= action['startTime']:
      matrix = vtk.vtkMatrix4x4()
      startTransform.GetMatrixTransformFromParent(matrix)
      targetTransform.SetMatrixTransformFromParent(matrix)
    elif scriptTime >= action['endTime']:
      matrix = vtk.vtkMatrix4x4()
      endTransform.GetMatrixTransformFromParent(matrix)
      targetTransform.SetMatrixTransformFromParent(matrix)
    else:
      actionTime = scriptTime - action['startTime']
      duration = action['endTime'] - action['startTime']
      fraction = actionTime / duration
      startMatrix = vtk.vtkMatrix4x4()
      startTransform.GetMatrixTransformFromParent(startMatrix)
      endMatrix = vtk.vtkMatrix4x4()
      endTransform.GetMatrixTransformFromParent(endMatrix)
      targetMatrix = vtk.vtkMatrix4x4()
      targetMatrix.DeepCopy(startMatrix)
      for i in range(3):
        start = startMatrix.GetElement(i,3)
        end = endMatrix.GetElement(i,3)
        delta = fraction * (end-start)
        # TODO: add interpolation and ease in/out options
        targetMatrix.SetElement(i,3, start + delta)
      targetTransform.SetMatrixTransformFromParent(targetMatrix)

class CameraRotationAction(AnimatorAction):
  """Defines an animation of a transform"""
  def __init__(self):
    super(CameraRotationAction,self).__init__()
    self.name = "CameraRotationAction"

  def react(self, action, scriptTime):
    referenceCamera = slicer.mrmlScene.GetNodeByID(action['referenceCameraID'])
    targetCamera = slicer.mrmlScene.GetNodeByID(action['targetCameraID'])

    targetCamera.GetCamera().DeepCopy(referenceCamera.GetCamera())
    if scriptTime <= action['startTime']:
      return
    else:
      actionTime = scriptTime - action['startTime']
      if actionTime > action['endTime']:
        actionTime = action['endTime'] # clamp to rotation at end
      angle = actionTime * action['degreesPerSecond']
      targetCamera.GetCamera().Azimuth(angle)
      targetCamera.GetCamera().OrthogonalizeViewUp()
      # TODO: this->Renderer->UpdateLightsGeometryToFollowCamera()

class ROIAction(AnimatorAction):
  """Defines an animation of an roi (e.g. for volume cropping)"""
  def __init__(self):
    super(ROIAction,self).__init__()
    self.name = "ROIAction"

  def react(self, action, scriptTime):
    startROI = slicer.mrmlScene.GetNodeByID(action['startROIID'])
    endROI = slicer.mrmlScene.GetNodeByID(action['endROIID'])
    targetROI = slicer.mrmlScene.GetNodeByID(action['targetROIID'])
    start = [0.,]*3
    end = [0.,]*3
    target = [0,]*3
    if scriptTime <= action['startTime']:
      startROI.GetXYZ(start)
      targetROI.SetXYZ(start)
      startROI.GetRadiusXYZ(start)
      targetROI.SetRadiusXYZ(start)
    elif scriptTime >= action['endTime']:
      endROI.GetXYZ(end)
      targetROI.SetXYZ(end)
      endROI.GetRadiusXYZ(end)
      targetROI.SetRadiusXYZ(end)
    else:
      actionTime = scriptTime - action['startTime']
      duration = action['endTime'] - action['startTime']
      fraction = actionTime / duration
      startROI.GetXYZ(start)
      endROI.GetXYZ(end)
      for i in range(3):
        target[i] = start[i] + fraction * (end[i]-start[i])
      targetROI.SetXYZ(target)
      startROI.GetRadiusXYZ(start)
      endROI.GetRadiusXYZ(end)
      for i in range(3):
        target[i] = start[i] + fraction * (end[i]-start[i])
      targetROI.SetRadiusXYZ(target)

class VolumePropertyAction(AnimatorAction):
  """Defines an animation of an roi (e.g. for volume cropping)"""
  def __init__(self):
    super(VolumePropertyAction,self).__init__()
    self.name = "VolumePropertyAction"

  def react(self, action, scriptTime):
    startVolumeProperty = slicer.mrmlScene.GetNodeByID(action['startVolumePropertyID'])
    endVolumeProperty = slicer.mrmlScene.GetNodeByID(action['endVolumePropertyID'])
    targetVolumeProperty = slicer.mrmlScene.GetNodeByID(action['targetVolumePropertyID'])
    if scriptTime <= action['startTime']:
      targetVolumeProperty.CopyParameterSet(startVolumeProperty)
    elif scriptTime >= action['endTime']:
      targetVolumeProperty.CopyParameterSet(endVolumeProperty)
    else:
      actionTime = scriptTime - action['startTime']
      duration = action['endTime'] - action['startTime']
      fraction = actionTime / duration
      disabledModify = targetVolumeProperty.StartModify()
      targetVolumeProperty.CopyParameterSet(startVolumeProperty)
      # interpolate the scalar opacity
      startScalarOpacity = startVolumeProperty.GetScalarOpacity()
      endScalarOpacity = endVolumeProperty.GetScalarOpacity()
      targetScalarOpacity = targetVolumeProperty.GetScalarOpacity()
      nodeElementCount = 4
      startValue = [0.,]*nodeElementCount
      endValue = [0.,]*nodeElementCount
      targetValue = [0.,]*nodeElementCount
      for index in range(startScalarOpacity.GetSize()):
        startScalarOpacity.GetNodeValue(index, startValue)
        endScalarOpacity.GetNodeValue(index, endValue)
        for i in range(nodeElementCount):
          targetValue[i] = startValue[i] + fraction * (endValue[i]-startValue[i])
        targetScalarOpacity.SetNodeValue(index, targetValue)
      # interpolate the color transfer
      startColor = startVolumeProperty.GetColor()
      endColor = endVolumeProperty.GetColor()
      targetColor = targetVolumeProperty.GetColor()
      nodeElementCount = 6
      startValue = [0.,]*nodeElementCount
      endValue = [0.,]*nodeElementCount
      targetValue = [0.,]*nodeElementCount
      for index in range(startColor.GetSize()):
        startColor.GetNodeValue(index, startValue)
        endColor.GetNodeValue(index, endValue)
        for i in range(nodeElementCount):
          targetValue[i] = startValue[i] + fraction * (endValue[i]-startValue[i])
        targetColor.SetNodeValue(index, targetValue)
      targetVolumeProperty.EndModify(disabledModify)



# add an module-specific dict for any module other to add animator plugins.
# these must be subclasses (or duck types) of the
# AnimatorAction class below.  Dict keys are action types
# and values are classes
try:
  slicer.modules.animatorActionPlugins
except AttributeError:
  slicer.modules.animatorActionPlugins = {}
slicer.modules.animatorActionPlugins['TranslationAction'] = TranslationAction
slicer.modules.animatorActionPlugins['CameraRotationAction'] = CameraRotationAction
slicer.modules.animatorActionPlugins['ROIAction'] = ROIAction
slicer.modules.animatorActionPlugins['VolumePropertyAction'] = VolumePropertyAction


#
# Animator
#

class Animator(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Animator"
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

    self.duration = ctk.ctkDoubleSpinBox()
    self.duration.suffix = " seconds"
    self.duration.decimals = 1
    self.duration.minimum = 1
    self.duration.value = 5

    parametersFormLayout.addRow("Duration", self.duration)
    parametersFormLayout.addRow(self.sequencePlay)
    parametersFormLayout.addRow(self.sequenceSeek)

    #
    # Actions Area
    #
    actionsCollapsibleButton = ctk.ctkCollapsibleButton()
    actionsCollapsibleButton.text = "Actions"
    self.layout.addWidget(actionsCollapsibleButton)

    # Layout within the dummy collapsible button
    self.actionsFormLayout = qt.QFormLayout(actionsCollapsibleButton)


    # connections
    self.animationSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)

    # Add vertical spacer
    self.layout.addStretch(1)

  def cleanup(self):
    pass

  def onSelect(self):
    sequenceBrowserNode = None
    sequenceNode = None
    self.actionsFormLayout.removeWidget(self.actionsFormLayout.itemAt(0))
    self.animatorActionsGUI = None
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

      self.animatorActionsGUI = AnimatorActionsGUI(animationNode)
      self.actionsFormLayout.addRow(self.animatorActionsGUI.buildUI())

    self.sequencePlay.setMRMLSequenceBrowserNode(sequenceBrowserNode)
    self.sequenceSeek.setMRMLSequenceBrowserNode(sequenceBrowserNode)

class AnimatorActionsGUI(object):
  """Manage the UI elements for animation script
     Gets the script from the animationNode and
     returns a QWidget.
     Updates animation node script based on events from UI.

     TODO: this is hard coded for now, but can be generalized
     based on experience.
  """
  def __init__(self, animationNode):
    self.animationNode = animationNode

  def buildUI(self):
    logic = AnimatorLogic()
    script = logic.getScript(self.animationNode)
    actions = logic.getActions(self.animationNode)
    self.scrollArea = qt.QScrollArea()
    self.widget = qt.QWidget(self.scrollArea)
    self.scrollArea.widgetResizable = True
    self.scrollArea.setVerticalScrollBarPolicy(qt.Qt.ScrollBarAsNeeded)
    self.layout = qt.QFormLayout()
    self.widget.setLayout(self.layout)
    for action in actions:
      editButton = qt.QPushButton(action['name'])
      editButton.connect('clicked()', lambda action=action : self.onEdit(action))
      self.layout.addRow(editButton)
      duration = ctk.ctkDoubleRangeSlider()
      duration.maximum = script['duration']
      duration.minimumValue = action['startTime']
      duration.maximumValue = action['endTime']
      duration.orientation = qt.Qt.Horizontal
      self.layout.addRow(duration)
    return self.widget

  def onEdit(self, action = {}):
    dialog = qt.QDialog(slicer.util.mainWindow())
    layout = qt.QFormLayout(dialog)

    label = qt.QLabel(action['name'])
    layout.addRow("Edit properties of:",  label )

    # TODO: make UIs for each of the pre-defined action types

    colorSelector = slicer.qMRMLColorTableComboBox()
    colorSelector.nodeTypes = ["vtkMRMLColorNode"]
    colorSelector.hideChildNodeTypes = ("vtkMRMLDiffusionTensorDisplayPropertiesNode", "vtkMRMLProceduralColorNode", "")
    colorSelector.addEnabled = False
    colorSelector.removeEnabled = False
    colorSelector.noneEnabled = False
    colorSelector.selectNodeUponCreation = True
    colorSelector.showHidden = True
    colorSelector.showChildNodeTypes = True
    colorSelector.setMRMLScene( slicer.mrmlScene )
    colorSelector.setToolTip( "Pick the table of structures you wish to edit" )
    layout.addRow( colorSelector )

    buttonBox = qt.QDialogButtonBox()
    buttonBox.setStandardButtons(qt.QDialogButtonBox.Ok |
                                      qt.QDialogButtonBox.Cancel)
    layout.addRow(buttonBox)

    buttonBox.button(qt.QDialogButtonBox.Ok).setToolTip("Use currently selected color node.")
    buttonBox.button(qt.QDialogButtonBox.Cancel).setToolTip("Cancel current operation.")

    buttonBox.connect("accepted()", lambda : self.accept(dialog))
    buttonBox.connect("rejected()", dialog, "reject()")

    dialog.exec_()

  def accept(self, dialog):
    print(dialog)

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
    actions = script['actions'] if "actions" in script else []
    return(actions)

  def addAction(self, animationNode, action):
    """Add an action to the script """
    script = self.getScript(animationNode)
    actions = self.getActions(animationNode)
    actions.append(action)
    script['actions'] = actions
    self.setScript(animationNode, script)

  def compileScript(self, animationNode):
    """Convert the node's script into sequences and a sequence browser node.
       Returns the sequenceBrowserNode.
    """
    sequenceBrowserNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLSequenceBrowserNode')
    sequenceBrowserNode.SetName(animationNode.GetName() + "-Browser")
    sequenceBrowserNode.SetPlaybackItemSkippingEnabled(False)

    sequenceNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLSequenceNode')
    sequenceNode.SetIndexType(sequenceNode.NumericIndex)
    sequenceNode.SetName(animationNode.GetName() + "-TimingSequence")
    sequenceBrowserNode.AddSynchronizedSequenceNode(sequenceNode)

    # create on data node per frame of the script.
    # these are used to synchronize the animation
    # but don't hold any other data
    script = self.getScript(animationNode)
    frames = script['fps'] * script['duration']
    spf = 1. / script['fps']
    for frame in range(math.ceil(frames)):
      scriptTime = frame * spf
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
    # first, get some data and make it visible
    #
    import SampleData
    mrHead = SampleData.downloadSample('MRHead')
    slicer.util.delayDisplay("Head downloaded...",10)

    slicer.util.mainWindow().moduleSelector().selectModule('VolumeRendering')
    volumeRenderingWidgetRep = slicer.modules.volumerendering.widgetRepresentation()
    volumeRenderingWidgetRep.setMRMLVolumeNode(mrHead)

    volumeRenderingNode = slicer.mrmlScene.GetFirstNodeByName('VolumeRendering')
    volumeRenderingNode.SetVisibility(1)
    volumeRenderingNode.SetShading(False)
    slicer.util.mainWindow().moduleSelector().selectModule('Animator')

    self.delayDisplay('Volume rendering on')

    #
    # set up an animation
    #
    animationNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLScriptedModuleNode')
    animationNode.SetName('SelfTest Animation')
    animationNode.SetAttribute('ModuleName', 'Animation')

    logic = AnimatorLogic()

    script = {}
    script['title'] = "SelfTest Script"
    script['duration'] = 5.5 # in seconds
    script['fps'] = 30
    logic.setScript(animationNode, script)

    #
    # set up a translation action
    #
    startTransform = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode')
    startTransform.SetName('Start Transform')
    endTransform = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode')
    endTransform.SetName('End Transform')
    targetTransform = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode')
    targetTransform.SetName('Animated Transform')

    matrix = vtk.vtkMatrix4x4()
    matrix.SetElement(0,3, 10)
    matrix.SetElement(1,3, 5)
    matrix.SetElement(2,3, 15)
    endTransform.SetMatrixTransformFromParent(matrix)

    mrHead.SetAndObserveTransformNodeID(targetTransform.GetID())

    translationAction = {
      'name': 'Translation',
      'class': 'TranslationAction',
      'id': 'translation1',
      'startTime': 4,
      'endTime': 5,
      'interpolation': 'linear',
      'startTransformID': startTransform.GetID(),
      'endTransformID': endTransform.GetID(),
      'targetTransformID': targetTransform.GetID(),
    }

    logic.addAction(animationNode, translationAction)

    #
    # set up a camera rotation action
    #
    layoutManager = slicer.app.layoutManager()
    threeDView = layoutManager.threeDWidget(0).threeDView()
    targetCamera = threeDView.interactorStyle().GetCameraNode()
    referenceCamera = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLCameraNode')
    referenceCamera.SetName('referenceCamera')
    referenceCamera.GetCamera().DeepCopy(targetCamera.GetCamera())
    cameraRotationAction = {
      'name': 'CameraRotation',
      'class': 'CameraRotationAction',
      'id': 'cameraRotation1',
      'startTime': .1,
      'endTime': 4,
      'interpolation': 'linear',
      'referenceCameraID': referenceCamera.GetID(),
      'targetCameraID': targetCamera.GetID(),
      'degreesPerSecond': 90,
    }

    logic.addAction(animationNode, cameraRotationAction)

    #
    # set up an ROI action
    #
    startROI = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLAnnotationROINode')
    startROI.SetName('Start ROI')
    endROI = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLAnnotationROINode')
    endROI.SetName('End ROI')
    for roi in [startROI, endROI]:
      for index in range(roi.GetNumberOfDisplayNodes()):
        roi.GetNthDisplayNode(index).SetVisibility(False)
    targetROI = volumeRenderingNode.GetROINode()
    volumeRenderingNode.SetCroppingEnabled(True)

    start = [0.,]*3
    targetROI.GetXYZ(start)
    startROI.SetXYZ(start)
    endROI.SetXYZ(start)
    targetROI.GetRadiusXYZ(start)
    startROI.SetRadiusXYZ(start)
    end = [0.,]*3
    for i in range(3):
      end[i] = start[i] / 2.
    endROI.SetRadiusXYZ(end)

    roiAction = {
      'name': 'ROI',
      'class': 'ROIAction',
      'id': 'roi1',
      'startTime': 1,
      'endTime': 4,
      'interpolation': 'linear',
      'startROIID': startROI.GetID(),
      'endROIID': endROI.GetID(),
      'targetROIID': targetROI.GetID(),
    }

    logic.addAction(animationNode, roiAction)

    #
    # set up a volume property action
    #
    startVolumeProperty = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLVolumePropertyNode')
    startVolumeProperty.SetName('Start VolumeProperty')
    endVolumeProperty = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLVolumePropertyNode')
    endVolumeProperty.SetName('End VolumeProperty')
    targetVolumeProperty = volumeRenderingNode.GetVolumePropertyNode()

    startVolumeProperty.CopyParameterSet(targetVolumeProperty)
    endVolumeProperty.CopyParameterSet(targetVolumeProperty)

    endScalarOpacity = endVolumeProperty.GetScalarOpacity()
    nodeElementCount = 4
    endValue = [0,]*nodeElementCount
    endScalarOpacity.GetNodeValue(2, endValue)
    endValue[0] = 250
    endValue[1] = 0.25
    endScalarOpacity.SetNodeValue(2, endValue)

    endColor = endVolumeProperty.GetColor()
    nodeElementCount = 6
    endValue = [0.,]*nodeElementCount
    endColor.GetNodeValue(5, endValue)
    print(endColor)
    print(endValue)
    endValue[0] = 115.
    endValue[1] = 1.
    endValue[2] = 1.
    endValue[3] = 1.
    endColor.SetNodeValue(5, endValue)

    volumePropertyAction = {
      'name': 'Volume Property',
      'class': 'VolumePropertyAction',
      'id': 'volumeProperty1',
      'startTime': 0,
      'endTime': 1,
      'interpolation': 'linear',
      'startVolumePropertyID': startVolumeProperty.GetID(),
      'endVolumePropertyID': endVolumeProperty.GetID(),
      'targetVolumePropertyID': targetVolumeProperty.GetID(),
    }

    logic.addAction(animationNode, volumePropertyAction)

    #
    # set up the animation and turn it on
    #
    sequenceBrowserNode = logic.compileScript(animationNode)

    sequenceNodes = vtk.vtkCollection()
    sequenceBrowserNode.GetSynchronizedSequenceNodes(sequenceNodes, True) # include master
    sequenceNode = sequenceNodes.GetItemAsObject(0)

    animationNode.SetAttribute('Animator.sequenceBrowserNodeID', sequenceBrowserNode.GetID())
    animationNode.SetAttribute('Animator.sequenceNodeID', sequenceNode.GetID())

    slicer.modules.AnimatorWidget.animationSelector.setCurrentNode(animationNode)

    sequenceBrowserNode.SetPlaybackActive(True)

    self.delayDisplay('Test passed!', 10)
