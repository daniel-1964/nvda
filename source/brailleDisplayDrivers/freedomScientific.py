#brailleDisplayDrivers/freedomScientific.py
#A part of NonVisual Desktop Access (NVDA)
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.
#Copyright (C) 2008-2017 NV Access Limited

from ctypes import *
from ctypes.wintypes import *
from collections import OrderedDict
import itertools
import hwPortUtils
import braille
import inputCore
from baseObject import ScriptableObject
from winUser import WNDCLASSEXW, WNDPROC, LRESULT, HCURSOR
from logHandler import log
import brailleInput

#Try to load the fs braille dll
try:
	fsbLib=windll.fsbrldspapi
except:
	fsbLib=None

#Map the needed functions in the fs braille dll
if fsbLib:
	fbOpen=getattr(fsbLib,'_fbOpen@12')
	fbGetCellCount=getattr(fsbLib,'_fbGetCellCount@4')
	fbWrite=getattr(fsbLib,'_fbWrite@16')
	fbClose=getattr(fsbLib,'_fbClose@4')
	fbConfigure=getattr(fsbLib, '_fbConfigure@8')
	fbGetDisplayName=getattr(fsbLib, "_fbGetDisplayName@12")
	fbGetFirmwareVersion=getattr(fsbLib,  "_fbGetFirmwareVersion@12")
	fbBeep=getattr(fsbLib, "_fbBeep@4")
	fbSetVariBraille=getattr(fsbLib,'_fbSetVariBraille@8')

FB_INPUT=1
FB_DISCONNECT=2
FB_EXT_KEY=3

LRESULT=c_long
HCURSOR=c_long

# Firmness setting
FB_FIRMNESS_MINIMUM=0x00
FB_FIRMNESS_LOW=1
FB_FIRMNESS_MEDIUM=2
FB_FIRMNESS_HIGH=3
FB_FIRMNESS_MAXIMUM=4

appInstance=windll.kernel32.GetModuleHandleW(None)

nvdaFsBrlWm=windll.user32.RegisterWindowMessageW(u"nvdaFsBrlWm")

inputType_keys=3
inputType_routing=4
inputType_wizWheel=5

# Names of freedom scientific bluetooth devices
bluetoothNames = (
	"F14", "Focus 14 BT",
	"Focus 40 BT",
	"Focus 80 BT",
)

keysPressed=0
extendedKeysPressed=0
@WNDPROC
def nvdaFsBrlWndProc(hwnd,msg,wParam,lParam):
	global keysPressed, extendedKeysPressed
	keysDown=0
	extendedKeysDown=0
	if msg==nvdaFsBrlWm and wParam in (FB_INPUT, FB_EXT_KEY):
		if wParam==FB_INPUT:
			inputType=lParam&0xff
			if inputType==inputType_keys:
				keyBits=lParam>>8
				keysDown=keyBits
				keysPressed |= keyBits
			elif inputType==inputType_routing:
				routingIndex=(lParam>>8)&0xff
				isRoutingPressed=bool((lParam>>16)&0xff)
				isTopRoutingRow=bool((lParam>>24)&0xff)
				if isRoutingPressed:
					gesture=RoutingGesture(routingIndex,isTopRoutingRow)
					try:
						inputCore.manager.executeGesture(gesture)
					except inputCore.NoInputGestureAction:
						pass
			elif inputType==inputType_wizWheel:
				numUnits=(lParam>>8)&0x7
				isRight=bool((lParam>>12)&1)
				isDown=bool((lParam>>11)&1)
				#Right's up and down are rversed, but NVDA does not want this
				if isRight: isDown=not isDown
				for unit in xrange(numUnits):
					gesture=WizWheelGesture(isDown,isRight)
					try:
						inputCore.manager.executeGesture(gesture)
					except inputCore.NoInputGestureAction:
						pass
		elif wParam==FB_EXT_KEY:
			keyBits=lParam>>4
			extendedKeysDown=keyBits
			extendedKeysPressed|=keyBits
		if keysDown==0 and extendedKeysDown==0 and (keysPressed!=0 or extendedKeysPressed!=0):
			gesture=KeyGesture(keysPressed,extendedKeysPressed)
			keysPressed=extendedKeysPressed=0
			try:
				inputCore.manager.executeGesture(gesture)
			except inputCore.NoInputGestureAction:
				pass
		return 0
	else:
		return windll.user32.DefWindowProcW(hwnd,msg,wParam,lParam)

nvdaFsBrlWndCls=WNDCLASSEXW()
nvdaFsBrlWndCls.cbSize=sizeof(nvdaFsBrlWndCls)
nvdaFsBrlWndCls.lpfnWndProc=nvdaFsBrlWndProc
nvdaFsBrlWndCls.hInstance=appInstance
nvdaFsBrlWndCls.lpszClassName=u"nvdaFsBrlWndCls"

class BrailleDisplayDriver(braille.BrailleDisplayDriver,ScriptableObject):

	name="freedomScientific"
	# Translators: Names of braille displays.
	description=_("Freedom Scientific Focus/PAC Mate series")
	firmness=FB_FIRMNESS_MAXIMUM

	@classmethod
	def check(cls):
		return bool(fsbLib)

	@classmethod
	def getPossiblePorts(cls):
		ports = OrderedDict([cls.AUTOMATIC_PORT, ("USB", "USB",)])
		try:
			cls._getBluetoothPorts().next()
			ports["bluetooth"] = "Bluetooth"
		except StopIteration:
			pass
		return ports

	@classmethod
	def _getBluetoothPorts(cls):
		for p in hwPortUtils.listComPorts():
			try:
				btName = p["bluetoothName"]
			except KeyError:
				continue
			if not any(btName == prefix or btName.startswith(prefix + " ") for prefix in bluetoothNames):
				continue
			yield p["port"].encode("mbcs")

	wizWheelActions=[
		# Translators: The name of a key on a braille display, that scrolls the display to show previous/next part of a long line.
		(_("display scroll"),("globalCommands","GlobalCommands","braille_scrollBack"),("globalCommands","GlobalCommands","braille_scrollForward")),
		# Translators: The name of a key on a braille display, that scrolls the display to show the next/previous line.
		(_("line scroll"),("globalCommands","GlobalCommands","braille_previousLine"),("globalCommands","GlobalCommands","braille_nextLine")),
	]

	def __init__(self, port="auto"):
		self.leftWizWheelActionCycle=itertools.cycle(self.wizWheelActions)
		action=self.leftWizWheelActionCycle.next()
		self.gestureMap.add("br(freedomScientific):leftWizWheelUp",*action[1])
		self.gestureMap.add("br(freedomScientific):leftWizWheelDown",*action[2])
		self.rightWizWheelActionCycle=itertools.cycle(self.wizWheelActions)
		action=self.rightWizWheelActionCycle.next()
		self.gestureMap.add("br(freedomScientific):rightWizWheelUp",*action[1])
		self.gestureMap.add("br(freedomScientific):rightWizWheelDown",*action[2])
		super(BrailleDisplayDriver,self).__init__()
		self._messageWindowClassAtom=windll.user32.RegisterClassExW(byref(nvdaFsBrlWndCls))
		self._messageWindow=windll.user32.CreateWindowExW(0,self._messageWindowClassAtom,u"nvdaFsBrlWndCls window",0,0,0,0,0,None,None,appInstance,None)
		if port == "auto":
			portsToTry = itertools.chain(["USB"], self._getBluetoothPorts())
		elif port == "bluetooth":
			portsToTry = self._getBluetoothPorts()
		else: # USB
			portsToTry = ["USB"]
		fbHandle=-1
		for port in portsToTry:
                        log.debug("Trying port %s", port)
			fbHandle=fbOpen(port,self._messageWindow,nvdaFsBrlWm)
			if fbHandle!=-1:
				break
		if fbHandle==-1:
			windll.user32.DestroyWindow(self._messageWindow)
			windll.user32.UnregisterClassW(self._messageWindowClassAtom,appInstance)
			raise RuntimeError("No display found")
		self.fbHandle=fbHandle
		self._configureDisplay()
		numCells=self.numCells
		for i in xrange(1, 6):
			self.gestureMap.add("br(freedomScientific):topRouting%d"%i,"globalCommands","GlobalCommands","braille_scrollBack")
		for i in xrange(numCells, numCells - 5, -1):
			self.gestureMap.add("br(freedomScientific):topRouting%d"%i,"globalCommands","GlobalCommands","braille_scrollForward")
		for i in xrange((numCells / 2) + 1, (numCells / 2) + 6):
			self.gestureMap.add("br(freedomScientific):topRouting%d"%i,"globalCommands","GlobalCommands","braille_nextLine")
		for i in xrange(numCells / 2, (numCells / 2) - 5, -1):
			self.gestureMap.add("br(freedomScientific):topRouting%d"%i,"globalCommands","GlobalCommands","braille_previousLine")

	def terminate(self):
		super(BrailleDisplayDriver,self).terminate()
		fbClose(self.fbHandle)
		windll.user32.DestroyWindow(self._messageWindow)
		windll.user32.UnregisterClassW(self._messageWindowClassAtom,appInstance)

	def _get_numCells(self):
		return fbGetCellCount(self.fbHandle)

	def display(self,cells):
		cells="".join([chr(x) for x in cells])
		fbWrite(self.fbHandle,0,len(cells),cells)

	def _configureDisplay(self):
		# See what display we are connected to
		displayName= firmwareVersion=""
		buf = create_string_buffer(16)
		if fbGetDisplayName(self.fbHandle, buf, 16):
			displayName=buf.value
		if fbGetFirmwareVersion(self.fbHandle, buf, 16):
			firmwareVersion=buf.value
		if displayName and firmwareVersion and displayName=="Focus" and ord(firmwareVersion[0])>=ord('3'):
			# Focus 2 or later. Make sure extended keys support is enabled.
			log.debug("Activating extended keys on freedom Scientific display. Display name: %s, firmware version: %s.", displayName, firmwareVersion)
			fbConfigure(self.fbHandle, 0x02)
			log.debug("Setting firmness to %d on freedom Scientific display. Display name: %s, firmwareversion: %s.", self.firmness, displayName, firmwareVersion)
			fbSetVariBraille(self.fbHandle, self.firmness * 0xff / FB_FIRMNESS_MAXIMUM)

	def script_toggleLeftWizWheelAction(self,gesture):
		action=self.leftWizWheelActionCycle.next()
		self.gestureMap.add("br(freedomScientific):leftWizWheelUp",*action[1],replace=True)
		self.gestureMap.add("br(freedomScientific):leftWizWheelDown",*action[2],replace=True)
		braille.handler.message(action[0])

	def script_toggleRightWizWheelAction(self,gesture):
		action=self.rightWizWheelActionCycle.next()
		self.gestureMap.add("br(freedomScientific):rightWizWheelUp",*action[1],replace=True)
		self.gestureMap.add("br(freedomScientific):rightWizWheelDown",*action[2],replace=True)
		braille.handler.message(action[0])

	__gestures={
		"br(freedomScientific):leftWizWheelPress":"toggleLeftWizWheelAction",
		"br(freedomScientific):rightWizWheelPress":"toggleRightWizWheelAction",
	}

	gestureMap=inputCore.GlobalGestureMap({
		"globalCommands.GlobalCommands" : {
			"braille_routeTo":("br(freedomScientific):routing",),
			"braille_scrollBack" : ("br(freedomScientific):leftAdvanceBar", "br(freedomScientific):leftBumperBarUp","br(freedomScientific):rightBumperBarUp",),
			"braille_scrollForward" : ("br(freedomScientific):rightAdvanceBar","br(freedomScientific):leftBumperBarDown","br(freedomScientific):rightBumperBarDown",),
			"braille_previousLine" : ("br(freedomScientific):leftRockerBarUp", "br(freedomScientific):rightRockerBarUp",),
			"braille_nextLine" : ("br(freedomScientific):leftRockerBarDown", "br(freedomScientific):rightRockerBarDown",),
			"kb:alt+a" : ("br(freedomscientific):dot1+rightShiftKey",),
			"kb:alt+b" : ("br(freedomscientific):dot2+dot1+rightShiftKey",),
			"kb:alt+c" : ("br(freedomscientific):dot1+dot4+rightShiftKey",),
			"kb:alt+d" : ("br(freedomscientific):dot1+dot4+dot5+rightShiftKey",),
			"kb:alt+e" : ("br(freedomscientific):dot1+dot5+rightShiftKey",),
			"kb:alt+f" : ("br(freedomscientific):dot1+dot2+dot4+rightShiftKey",),
			"kb:alt+g" : ("br(freedomscientific):dot2+dot1+rightShiftKey+dot5+dot4",),
			"kb:alt+h" : ("br(freedomscientific):dot2+dot1+rightShiftKey+dot5",),
			"kb:alt+i" : ("br(freedomscientific):dot2+rightShiftKey+dot4",),
			"kb:alt+j" : ("br(freedomscientific):dot2+rightShiftKey+dot5+dot4",),
			"kb:alt+k" : ("br(freedomscientific):dot3+dot1+rightShiftKey",),
			"kb:alt+l" : ("br(freedomscientific):dot3+dot2+dot1+rightShiftKey",),
			"kb:alt+m" : ("br(freedomscientific):dot3+dot1+rightShiftKey+dot4",),
			"kb:alt+n" : ("br(freedomscientific):dot3+d ot1+rightShiftKey+dot5+dot4",),
			"kb:alt+o" : ("br(freedomscientific):dot3+dot1+rightShiftKey+dot5",),
			"kb:alt+p" : ("br(freedomscientific):dot3+dot2+dot1+rightShiftKey+dot4",),
			"kb:alt+q" : ("br(freedomscientific):dot3+dot2+dot1+dot5+rightShiftKey+dot4",),
			"kb:alt+r" : ("br(freedomscientific):dot3+dot2+dot1+rightShiftKey+dot5",),
			"kb:alt+s" : ("br(freedomscientific):dot3+dot2+rightShiftKey+dot4",),
			"kb:alt+t" : ("br(freedomscientific):dot3+dot2+rightShiftKey+dot5+dot4",),
			"kb:alt+u" : ("br(freedomscientific):dot3+dot1+dot6+rightShiftKey",),
			"kb:alt+v" : ("br(freedomscientific):dot3+dot2+dot1+dot6+rightShiftKey",),
			"kb:alt+w" : ("br(freedomscientific):dot2+rightShiftKey+dot6+dot5+dot4",),
			"kb:alt+x" : ("br(freedomscientific):dot3+dot1+dot6+rightShiftKey+dot4",),
			"kb:alt+y" : ("br(freedomscientific):dot3+dot1+dot6+rightShiftKey+dot4+dot5",),
			"kb:alt+z" : ("br(freedomscientific):dot3+dot1+rightShiftKey+dot6+dot5",),
			"kb:control+a" : ("br(freedomscientific):dot1+dot8+dot7",),
			"kb:control+b" : ("br(freedomscientific):dot2+dot1+dot8+dot7",),
			"kb:control+c" : ("br(freedomscientific):dot1+dot8+dot7+dot4",),
			"kb:control+d" : ("br(freedomscientific):dot1+dot8+dot7+dot5+dot4",),
			"kb:control+e" : ("br(freedomscientific):dot1+dot8+dot7+dot5",),
			"kb:control+f" : ("br(freedomscientific):dot2+dot1+dot8+dot7+dot4",),
			"kb:control+g" : ("br(freedomscientific):dot2+dot1+dot7+dot5+dot4+dot8",),
			"kb:control+h" : ("br(freedomscientific):dot2+dot1+dot8+dot7+dot5",),
			"kb:control+i" : ("br(freedomscientific):dot2+dot8+dot7+dot4",),
			"kb:control+j" : ("br(freedomscientific):dot2+dot8+dot7+dot5+dot4",),
			"kb:control+k" : ("br(freedomscientific):dot3+dot1+dot8+dot7",),
			"kb:control+l" : ("br(freedomscientific):dot3+dot2+dot1+dot8+dot7",),
			"kb:control+m" : ("br(freedomscientific):dot3+dot1+dot8+dot7+dot4",),
			"kb:control+n" : ("br(freedomscientific):dot3+dot1+dot7+dot5+dot4+dot8",),
			"kb:control+o" : ("br(freedomscientific):dot3+dot1+dot8+dot7+dot5",),
			"kb:control+p" : ("br(freedomscientific):dot3+dot2+dot1+dot7+dot4+dot8",),
			"kb:control+q" : ("br(freedomscientific):dot3+dot2+dot1+dot7+dot5+dot4+dot8",),
			"kb:control+r" : ("br(freedomscientific):dot3+dot2+dot1+dot7+dot5+dot8",),
			"kb:control+s" : ("br(freedomscientific):dot3+dot2+dot8+dot7+dot4",),
			"kb:control+t" : ("br(freedomscientific):dot3+dot2+dot7+dot5+dot4+dot8",),
			"kb:control+u" : ("br(freedomscientific):dot3+dot1+dot8+dot7+dot6",),
			"kb:control+v" : ("br(freedomscientific):dot3+dot2+dot1+dot7+dot6+dot8",),
			"kb:control+w" : ("br(freedomscientific):dot2+dot7+dot6+dot5+dot4+dot8",),
			"kb:control+x" : ("br(freedomscientific):dot3+dot1+dot7+dot6+dot4+dot8",),
			"kb:control+y" : ("br(freedomscientific):dot3+dot1+dot7+dot6+dot5+dot4+dot8",),
			"kb:control+z" : ("br(freedomscientific):dot3+dot1+dot7+dot6+dot5+dot8",),
			"kb:f1" : ("br(freedomscientific):dot1+leftshiftkey",),
			"kb:f2" : ("br(freedomscientific):dot2+dot1+leftshiftkey",),
			"kb:f3" : ("br(freedomscientific):dot1+leftshiftkey+dot4",),
			"kb:f4" : ("br(freedomscientific):dot1+leftshiftkey+dot5+dot4",),
			"kb:f5" : ("br(freedomscientific):dot1+leftshiftkey+dot5",),
			"kb:f6" : ("br(freedomscientific):dot2+dot1+leftshiftkey+dot4",),
			"kb:f7" : ("br(freedomscientific):dot2+dot1+leftshiftkey+dot5+dot4",),
			"kb:f8" : ("br(freedomscientific):dot2+dot1+leftshiftkey+dot5",),
			"kb:f9" : ("br(freedomscientific):dot2+leftshiftkey+dot4",),
			"kb:f10" : ("br(freedomscientific):dot2+leftshiftkey+dot5+dot4",),
			"kb:f11" : ("br(freedomscientific):dot3+dot1+leftshiftkey",),
			"kb:f12" : ("br(freedomscientific):dot3+dot2+dot1+leftshiftkey",),
			"kb:shift+f1" : ("br(freedomscientific):dot1+dot7+leftshiftkey",),
			"kb:shift+f2" : ("br(freedomscientific):dot2+dot1+dot7+leftshiftkey",),
			"kb:shift+f3" : ("br(freedomscientific):dot1+dot7+leftshiftkey+dot4",),
			"kb:shift+f4" : ("br(freedomscientific):dot1+dot7+leftshiftkey+dot5+dot4",),
			"kb:shift+f5" : ("br(freedomscientific):dot1+dot7+leftshiftkey+dot5",),
			"kb:shift+f6" : ("br(freedomscientific):dot2+dot1+dot7+leftshiftkey+dot4",),
			"kb:shift+f7" : ("br(freedomscientific):dot2+dot1+dot7+dot5+dot4+leftshiftkey",),
			"kb:shift+f8" : ("br(freedomscientific):dot2+dot1+dot7+leftshiftkey+dot5",),
			"kb:shift+f9" : ("br(freedomscientific):dot2+leftshiftkey+dot7+dot4",),
			"kb:shift+f10" : ("br(freedomscientific):dot2+leftshiftkey+dot7+dot5+dot4",),
			"kb:shift+f11" : ("br(freedomscientific):dot3+dot1+dot7+leftshiftkey",),
			"kb:shift+f12" : ("br(freedomscientific):dot3+dot2+dot1+dot7+leftshiftkey",),
			"kb:control+f1" : ("br(freedomscientific):dot1+dot8+dot7+leftshiftkey",),
			"kb:control+f2" : ("br(freedomscientific):dot2+dot1+dot8+dot7+leftshiftkey",),
			"kb:control+f3" : ("br(freedomscientific):dot1+dot8+dot7+leftshiftkey+dot4",),
			"kb:control+f4" : ("br(freedomscientific):dot1+dot7+dot5+dot4+dot8+leftshiftkey",),
			"kb:control+f5" : ("br(freedomscientific):dot1+dot8+dot7+leftshiftkey+dot5",),
			"kb:control+f6" : ("br(freedomscientific):dot2+dot1+dot7+dot4+dot8+leftshiftkey",),
			"kb:control+f7" : ("br(freedomscientific):dot2+dot1+dot7+dot5+dot4+dot8+leftshiftkey",),
			"kb:control+f8" : ("br(freedomscientific):dot2+dot1+dot7+dot5+dot8+leftshiftkey",),
			"kb:control+f9" : ("br(freedomscientific):dot2+leftshiftkey+dot8+dot7+dot4",),
			"kb:control+f10" : ("br(freedomscientific):dot2+dot7+dot5+dot4+dot8+leftshiftkey",),
			"kb:control+f11" : ("br(freedomscientific):dot3+dot1+dot8+dot7+leftshiftkey",),
			"kb:control+f12" : ("br(freedomscientific):dot3+dot2+dot1+dot7+dot8+leftshiftkey",),
			"kb:alt+f1" : ("br(freedomscientific):dot1+dot8+leftshiftkey",),
			"kb:alt+f2" : ("br(freedomscientific):dot2+dot1+dot8+leftshiftkey",),
			"kb:alt+f3" : ("br(freedomscientific):dot1+dot8+leftshiftkey+dot4",),
			"kb:alt+f4" : ("br(freedomscientific):dot1+dot8+leftshiftkey+dot5+dot4",),
			"kb:alt+f5" : ("br(freedomscientific):dot1+dot8+leftshiftkey+dot5",),
			"kb:alt+f6" : ("br(freedomscientific):dot2+dot1+dot8+leftshiftkey+dot4",),
			"kb:alt+f7" : ("br(freedomscientific):dot2+dot1+dot5+dot4+dot8+leftshiftkey",),
			"kb:alt+f8" : ("br(freedomscientific):dot2+dot1+dot8+leftshiftkey+dot5",),
			"kb:alt+f9" : ("br(freedomscientific):dot2+leftshiftkey+dot8+dot4",),
			"kb:alt+f10" : ("br(freedomscientific):dot2+leftshiftkey+dot8+dot5+dot4",),
			"kb:alt+f11" : ("br(freedomscientific):dot3+dot1+dot8+leftshiftkey",),
			"kb:alt+f12" : ("br(freedomscientific):dot3+dot2+dot1+dot8+leftshiftkey",),
			"kb:backspace" : ("br(freedomscientific):leftshiftkey", "br(freedomScientific):dot7",),
			"kb:shift+alt+tab" : ("br(freedomscientific):dot2+dot1+dot6+dot5+braillespacebar",),
			"kb:enter" : ("br(freedomscientific):dot3+braillespacebar+dot5+dot4", "br(freedomscientific):leftshiftkey+rightShiftKey", "br(freedomScientific):dot8",),
			"kb:shift+enter" : ("br(freedomscientific):dot3+braillespacebar+dot7+dot5+dot4", "br(freedomscientific):leftshiftkey+dot7+rightShiftKey",),
			"kb:control+enter" : ("br(freedomscientific):dot3+dot7+dot5+dot4+braillespacebar+dot8", "br(freedomscientific):leftshiftkey+dot8+dot7+rightShiftKey",),
			"kb:alt+enter" : ("br(freedomscientific):dot3+braillespacebar+dot8+dot5+dot4", "br(freedomscientific):leftshiftkey+dot8+rightShiftKey",),
			"kb:escape" : ("br(freedomscientific):dot3+braillespacebar+dot1+dot6+dot5",),
			"kb:shift+escape" : ("br(freedomscientific):braillespacebar+dot1+dot7+dot5", "br(freedomscientific):dot3+dot1+dot7+dot6+dot5+braillespacebar",),
			"kb:control+escape" : ("br(freedomscientific):braillespacebar+dot1+dot8+dot7+dot5", "br(freedomscientific):dot3+dot1+dot7+dot6+dot5+braillespacebar+dot8",),
			"kb:alt+escape" : ("br(freedomscientific):braillespacebar+dot1+dot8+dot5", "br(freedomscientific):dot3+dot1+dot6+dot5+braillespacebar+dot8",),
			"kb:shift+space" : ("br(freedomscientific):braillespacebar+dot7",),
			"kb:control+space" : ("br(freedomscientific):braillespacebar+dot8+dot7",),
			"kb:alt+space" : ("br(freedomscientific):braillespacebar+dot8",),
			"kb:shift+upArrow" : ("br(freedomscientific):braillespacebar+dot1+dot7",),
			"kb:control+upArrow" : ("br(freedomscientific):braillespacebar+dot1+dot8+dot7",),
			"kb:alt+upArrow" : ("br(freedomscientific):braillespacebar+dot1+dot8",),
			"kb:shift+downArrow" : ("br(freedomscientific):braillespacebar+dot7+dot4",),
			"kb:control+downArrow" : ("br(freedomscientific):braillespacebar+dot8+dot7+dot4",),
			"kb:alt+downArrow" : ("br(freedomscientific):braillespacebar+dot8+dot4",),
			"kb:shift+leftArrow" : ("br(freedomscientific):dot3+braillespacebar+dot7",),
			"kb:alt+leftArrow" : ("br(freedomscientific):braillespacebar+dot3+dot8",),
			"kb:control+shift+leftArrow" : ("br(freedomscientific):braillespacebar+dot2+dot7",),
			"kb:control+alt+leftArrow" : ("br(freedomscientific):braillespacebar+dot8+dot2",),
			"kb:shift+rightArrow" : ("br(freedomscientific):braillespacebar+dot7+dot6",),
			"kb:alt+rightArrow" : ("br(freedomscientific):braillespacebar+dot8+dot6",),
			"kb:control+shift+rightArrow" : ("br(freedomscientific):braillespacebar+dot7+dot5",),
			"kb:control+alt+rightArrow" : ("br(freedomscientific):braillespacebar+dot8+dot5",),
			"kb:shift+home" : ("br(freedomscientific):dot3+braillespacebar+dot1+dot7",),
			"kb:alt+home" : ("br(freedomscientific):dot3+braillespacebar+dot1+dot8",),
			"kb:control+shift+home" : ("br(freedomscientific):braillespacebar+dot3+dot2+dot1+dot7",),
			"kb:control+alt+home" : ("br(freedomscientific):dot3+braillespacebar+dot1+dot8+dot2",),
			"kb:shift+end" : ("br(freedomscientific):braillespacebar+dot7+dot6+dot4",),
			"kb:alt+end" : ("br(freedomscientific):braillespacebar+dot8+dot6+dot4",),
			"kb:control+shift+end" : ("br(freedomscientific):braillespacebar+dot7+dot6+dot5+dot4",),
			"kb:control+alt+end" : ("br(freedomscientific):braillespacebar+dot8+dot6+dot5+dot4",),
			"kb:pageUp" : ("br(freedomscientific):braillespacebar+dot3+dot2",),
			"kb:shift+pageUp" : ("br(freedomscientific):braillespacebar+dot3+dot2+dot7",),
			"kb:control+pageUp" : ("br(freedomscientific):braillespacebar+dot3+dot2+dot7+dot8",),
			"kb:alt+pageUp" : ("br(freedomscientific):dot3+braillespacebar+dot8+dot2",),
			"kb:pageDown" : ("br(freedomscientific):braillespacebar+dot6+dot5",),
			"kb:shift+pageDown" : ("br(freedomscientific):braillespacebar+dot7+dot6+dot5",),
			"kb:control+pageDown" : ("br(freedomscientific):braillespacebar+dot8+dot7+dot6+dot5",),
			"kb:alt+pageDown" : ("br(freedomscientific):braillespacebar+dot8+dot6+dot5",),
			"kb:insert" : ("br(freedomscientific):braillespacebar+dot2+dot4",),
			"kb:shift+insert" : ("br(freedomscientific):braillespacebar+dot2+dot4+dot7",),
			"kb:control+insert" : ("br(freedomscientific):braillespacebar+dot8+dot2+dot4+dot7",),
			"kb:delete" : ("br(freedomscientific):rightShiftKey", "br(freedomscientific):braillespacebar+dot1+dot5+dot4",),
			"kb:shift+delete" : ("br(freedomscientific):braillespacebar+dot1+dot7+dot5+dot4",),
			"kb:control+delete" : ("br(freedomscientific):dot1+dot7+dot5+dot4+braillespacebar+dot8",),
			"kb:pause" : ("br(freedomscientific):dot3+dot2+dot1+leftshiftkey+dot4",),
			"kb:shift+pause" : ("br(freedomscientific):dot3+dot2+dot1+dot7+dot4+leftshiftkey",),
			"kb:control+break" : ("br(freedomscientific):dot3+dot2+dot1+dot7+dot4+dot8+leftshiftkey",),
			"kb:alt+pause" : ("br(freedomscientific):dot3+dot2+dot1+dot4+dot8+leftshiftkey",),
			"kb:applications" : ("br(freedomscientific):dot3+dot2+dot1+dot6+dot5+dot4+rightShiftKey", "br(freedomscientific):braillespacebar+dot3+dot2+dot1+dot4",),
			"kb:shift+tab": ("br(freedomScientific):dot1+dot2+brailleSpaceBar",),
			"kb:tab" : ("br(freedomScientific):dot4+dot5+brailleSpaceBar",),
			"kb:upArrow" : ("br(freedomScientific):dot1+brailleSpaceBar",),
			"kb:downArrow" : ("br(freedomScientific):dot4+brailleSpaceBar",),
			"kb:leftArrow" : ("br(freedomScientific):dot3+brailleSpaceBar",),
			"kb:rightArrow" : ("br(freedomScientific):dot6+brailleSpaceBar",),
			"kb:control+leftArrow" : ("br(freedomScientific):dot2+brailleSpaceBar",),
			"kb:control+rightArrow" : ("br(freedomScientific):dot5+brailleSpaceBar",),
			"kb:home" : ("br(freedomScientific):dot1+dot3+brailleSpaceBar",),
			"kb:control+home" : ("br(freedomScientific):dot1+dot2+dot3+brailleSpaceBar",),
			"kb:end" : ("br(freedomScientific):dot4+dot6+brailleSpaceBar",),
			"kb:control+end" : ("br(freedomScientific):dot4+dot5+dot6+brailleSpaceBar",),
			"kb:alt" : ("br(freedomScientific):dot1+dot3+dot4+brailleSpaceBar",),
			"kb:alt+tab" : ("br(freedomScientific):dot2+dot3+dot4+dot5+brailleSpaceBar",),
			"kb:alt+shift+tab" : ("br(freedomScientific):dot1+dot2+dot5+dot6+brailleSpaceBar",),
			"kb:win+tab" : ("br(freedomScientific):dot2+dot3+dot4+brailleSpaceBar",),
			"kb:escape" : ("br(freedomScientific):dot1+dot5+brailleSpaceBar",),
			"kb:windows" : ("br(freedomScientific):dot2+dot4+dot5+dot6+brailleSpaceBar",),
			"kb:windows+d" : ("br(freedomScientific):dot1+dot2+dot3+dot4+dot5+dot6+brailleSpaceBar",),
			"reportCurrentLine" : ("br(freedomScientific):dot1+dot4+brailleSpaceBar",),
			"showGui" :("br(freedomScientific):dot1+dot3+dot4+dot5+brailleSpaceBar",),
			"braille_toggleTether" : ("br(freedomScientific):leftGDFButton+rightGDFButton",),
			"navigatorObject_toFocus" : ("br(freedomscientific):rightgdfbutton",),
			"review_bottom" : ("br(freedomscientific):leftadvancebar+leftrockerbardown", "br(freedomscientific):rightadvancebar+rightrockerbardown", "br(freedomscientific):leftadvancebar+rightrockerbardown", "br(freedomscientific):rightadvancebar+leftrockerbardown",),
			"review_top" : ("br(freedomscientific):leftrockerbarup+rightadvancebar", "br(freedomscientific):leftgdfbutton", "br(freedomscientific):leftrockerbarup+leftadvancebar", "br(freedomscientific):rightrockerbarup+rightadvancebar", "br(freedomscientific):rightrockerbarup+leftadvancebar",),
			"review_endOfLine" : ("br(freedomscientific):rightadvancebar+rightgdfbutton", "br(freedomscientific):rightadvancebar+leftgdfbutton",),
			"review_startOfLine" : ("br(freedomscientific):leftadvancebar+rightgdfbutton", "br(freedomscientific):leftadvancebar+leftgdfbutton",),
			"reviewMode_previous" : ("br(freedomscientific):rightgdfbutton+leftrockerbardown", "br(freedomscientific):leftgdfbutton+rightrockerbardown",),
			"reviewMode_next" : ("br(freedomscientific):rightrockerbarup+leftgdfbutton", "br(freedomscientific):leftrockerbarup+rightgdfbutton",),
			"review_markStartForCopy" : ("br(freedomscientific):leftshiftkey+rightgdfbutton", "br(freedomscientific):leftshiftkey+leftgdfbutton",),
			"review_copy" : ("br(freedomscientific):rightgdfbutton+rightShiftKey", "br(freedomscientific):leftgdfbutton+rightShiftKey",),
			"toggleInputHelp" : ("br(freedomscientific):dot2+dot1+dot5+braillespacebar",),
		}
	})

class InputGesture(braille.BrailleDisplayGesture):
	source = BrailleDisplayDriver.name

class KeyGesture(InputGesture, brailleInput.BrailleInputGesture):

	keyLabels=[
		#Braille keys (byte 1)
		'dot1','dot2','dot3','dot4','dot5','dot6','dot7','dot8',
		#Assorted keys (byte 2)
		'leftWizWheelPress','rightWizWheelPress',
		'leftShiftKey','rightShiftKey',
		'leftAdvanceBar','rightAdvanceBar',
		None,
		'brailleSpaceBar',
		#GDF keys (byte 3)
		'leftGDFButton','rightGDFButton',
		None,
		'leftBumperBarUp','leftBumperBarDown','rightBumperBarUp','rightBumperBarDown',
	]
	extendedKeyLabels = [
	# Rocker bar keys.
	"leftRockerBarUp", "leftRockerBarDown", "rightRockerBarUp", "rightRockerBarDown",
	]

	def __init__(self,keyBits, extendedKeyBits):
		super(KeyGesture,self).__init__()
		keys=[self.keyLabels[num] for num in xrange(24) if (keyBits>>num)&1]
		extendedKeys=[self.extendedKeyLabels[num] for num in xrange(4) if (extendedKeyBits>>num)&1]
		self.id="+".join(keys+extendedKeys)
		# Don't say is this a dots gesture if some keys either from dots and space are pressed.
		if not extendedKeyBits and not keyBits & ~(0xff | (1 << 0xf)):
			self.dots = keyBits & 0xff
			# Is space?
			if keyBits & (1 << 0xf):
				self.space = True

class RoutingGesture(InputGesture):

	def __init__(self,routingIndex,topRow=False):
		if topRow:
			self.id="topRouting%d"%(routingIndex+1)
		else:
			self.id="routing"
			self.routingIndex=routingIndex
		super(RoutingGesture,self).__init__()

class WizWheelGesture(InputGesture):

	def __init__(self,isDown,isRight):
		which="right" if isRight else "left"
		direction="Down" if isDown else "Up"
		self.id="%sWizWheel%s"%(which,direction)
		super(WizWheelGesture,self).__init__()
