"""Used to control the stage"""

import stackless
import pygame
pygame.init()
import json
import collections
import serial
from structure import LightStructure, EventWrapper

screen = pygame.display.set_mode((640, 480))

def stringifyDict(dic):
    stringified = {}
    for key, value in dic.iteritems():
        stringified[str(key)] = value
    return stringified

class Page(object):
    """The class for a page of the show"""
    def __init__(self, idno=None, lights={}, links=None, time=-1, transition=None, notes=''):
        self.idno = idno
        self.links = links if links is not None else {'next': -1}
        self.lights = collections.defaultdict(lambda : 0)
        for key, value in stringifyDict(lights).iteritems():
            self.lights[key] = value
        self.time = time
        self.fullTime = time
        self.notes = notes
    def updateTime(self, time):
        if self.time < 0:
            return self.idno
        else:
            self.time -= time
            if self.time < 0:
                return self.links['timeout']

class Show(object):
    """The model for the show"""
    def __init__(self, fileName, channelList):
        self.loadFile(fileName)
        self.channelList = channelList
        self.currentPage = self.pages['0']
    def makeList(self):
        lst = [0] * 24
        for name, channel in self.channelList:
            lst[channel] = max(lst[channel], self.currentPage.lights[name])
        lst = [light * 255 / 100 for light in lst]
        return lst
    def updateTime(self, time):
        self.currentPage = self.pages[self.currentPage.updateTime(time)]
    def _createPage(self, prefix=''):
        i = 0
        while prefix + str(i) in self.pages:
            i += 1
        i = prefix + str(i)
        self.pages[i] = Page(i)
        nextPage = self._interrupt(i)
        self.currentPage.links['next'] = i
        return nextPage
    def moveForward(self):
        try:
            self.currentPage = self.pages[self.currentPage.links['next']]
        except KeyError:
            self.currentPage = self._createPage()
        if self.currentPage.links['next'] == -1:
            self._createPage()
    def moveBack(self):
        try:
            self.currentPage = self.pages[self.currentPage.links['previous']]
        except KeyError:
            pass
    def _interrupt(self, page):
        self.pages[page].links['previous'] = self.currentPage.idno
        self.pages[page].links['next'] = self.currentPage.links['next']
        return self.pages[page]
    def blackout(self):
        self.currentPage = self._interrupt('blackout')
    def hals(self):
        self.currentPage = self._interrupt('hals')
    def interrupt(self):
        nextLink = self.currentPage.links['next']
        nextPage = self._createPage('i')
        for key, value in self.pages['interrupt'].lights.iteritems():
            nextPage.lights[key] = value
            self.pages['interrupt'].lights[key] = 0
        self.currentPage = self._interrupt(nextPage.idno)
        nextPage.links['next'] = nextLink
        self.pages[nextLink].links['previous'] = nextPage.idno
    def save(self):
        pages = [{'idno': page.idno, 'lights': dict(page.lights),
                  'links': page.links, 'time': page.time,
                  'notes': page.notes}
                 for page in self.pages.itervalues()]
        fil = open(self.fileName, 'w')
        fil.write(json.dumps(pages, indent=1))
        fil.close()
    def loadFile(self, fileName):
        self.fileName = fileName
        try:
            fil = open(self.fileName)
            self.pages = dict((page['idno'], Page(**stringifyDict(page)))
                              for page in json.loads(fil.read()))
            fil.close()
        except IOError:
            self.pages = {'0': Page('0'),
                          'blackout': Page('blackout'),
                          'hals': Page('hals', {'ONHALS': 100,
                                                'OFFHALS': 100}),
                          'interrupt': Page('interrupt')}
    def getLights(self, transition=0):
        lights = collections.defaultdict(lambda : 0)
        currentLights = self.currentPage.lights
        try:
            nextLights = self.pages[self.currentPage.links['next']].lights
        except KeyError:
            nextLights = collections.defaultdict(lambda : 0)
        for key in currentLights:
            lights[key] = (currentLights[key] * (1 - transition) +
                           nextLights[key] * transition)
        for key in nextLights:
            if key not in lights:
                lights[key] = nextLights[key] * transition
        return lights
    def toggleIntensity(self, name, idno=None):
        page = self._getPage(idno)
        if page.lights[name] <= 50:
            page.lights[name] = 100
        elif page.lights[name] <= 75:
            page.lights[name] = 50
        else:
            page.lights[name] = 75
    def turnOff(self, name, idno=None):
        page = self._getPage(idno)
        page.lights[name] = 0
    def _getPage(self, idno):
        if idno is None:
            page = self.currentPage
        else:
            try:
                page = self.pages[idno]
            except KeyError:
                assert(idno == -1)
                page = self._createPage()
        return page
    def getPreview(self, idno):
        return self._getPage(idno).lights
    def delete(self):
         previousPage = self._getPage(self.currentPage.links['previous'])
         nextPage = self._getPage(self.currentPage.links['next'])
         previousPage.links['next'] = nextPage.idno
         nextPage.links['previous'] = previousPage.idno
         self.currentPage = nextPage
    def setNext(self, nextId):
        self.currentPage.links['next'] = nextId

class Action(object):
    """For actions to be taken on an event"""
    def __init__(self, test, function):
        self.test = test
        self.function = function
    def __call__(self, event):
        if self.test(event):
            self.function()
            return True
        return False

class MouseAction(object):
    """For the mouse actions"""
    def __init__(self, button, function):
        self.button = button
        self.function = function
    def __call__(self, event, name):
        if event.button == self.button and name:
            self.function(name)
            return True
        return False

class MacroRecorder(object):
    """Records and executes macros"""
    def __init__(self):
        self.refreshOutput = None
        self.macros = {'!': [],
                       '@': [],
                       '#': [],
                       '$': [],
                       '%': [],
                       '^': [],
                       '&': [],
                       '*': [],
                       '(': [],
                       ')': []}
        self.keyDic = {pygame.K_1: '!',
                       pygame.K_2: '@',
                       pygame.K_3: '#',
                       pygame.K_4: '$',
                       pygame.K_5: '%',
                       pygame.K_6: '^',
                       pygame.K_7: '&',
                       pygame.K_8: '*',
                       pygame.K_9: '(',
                       pygame.K_0: ')'}
        self.recording = False
    def updateEvents(self, getEvents):
        for event in getEvents():
            if event.type != pygame.KEYDOWN:
                continue
            if self.recording:
                if event.key == pygame.K_RETURN:
                    self.recording = False
            else:
                if event.unicode in self.macros:
                    self.recording = event.unicode
                    self.macros[self.recording] = []
                elif event.key in self.keyDic:
                    for function, args in self.macros[self.keyDic[event.key]]:
                        function(*args)
                    self.refreshOutput()
    def record(self, function, *args):
        if self.recording:
            self.macros[self.recording].append((function, args))
    def setRefreshOutput(self, refreshOutput):
        self.refreshOutput = refreshOutput
                    
class Controller(object):
    """The base for the controller classes"""
    def __init__(self, view, show, macros, output):
        self.running =  False
        self.output = output
        self.view = view
        self.mouseActions = (MouseAction(1, lambda name: show.toggleIntensity(name)),
                             MouseAction(3, lambda name: show.turnOff(name)))
        self.keyActions = ()
        self.macros = macros
        self.refreshOutput()
    def updateEvents(self, getEvents):
        """Converts events into actions"""
        changed = False
        for event in getEvents():
            if event.type == pygame.MOUSEBUTTONDOWN:
                name = self.view.getName(event.pos)
                for action in self.mouseActions:
                    if action(event, name):
                        self.macros.record(action.function, name)
                        changed = True
            elif event.type == pygame.KEYDOWN:
                for action in self.keyActions:
                    if action(event):
                        self.macros.record(action.function)
                        changed = True
        if changed:
            self.refreshOutput()
    def refreshOutput(self):
        if self.running and self.makeList():
            self.output.write(self.makeList())
    def makeList(self):
        return ''
    def setRunning(self, running):
        self.running = running

class MainController(Controller):
    """The controller for the stage itself"""
    def __init__(self, view, show, macros, output):
        Controller.__init__(self, view, show, macros, output)
        self.show = show
        testKey = lambda key: (lambda event: event.key == key)
        self.keyActions = (Action(testKey(pygame.K_PAGEDOWN),
                                  show.moveForward),
                           Action(testKey(pygame.K_PAGEUP), show.moveBack),
                           Action(testKey(pygame.K_i), show.interrupt),
                           Action(testKey(pygame.K_b), show.blackout),
                           Action(testKey(pygame.K_SPACE), show.hals),
                           Action(lambda event: event.unicode == u'', show.save),
                           Action(testKey(pygame.K_d), show.delete),
                           Action(testKey(pygame.K_r), self.refreshOutput),
                           Action(testKey(pygame.K_s), show.moveForward))
    def load(self):
        pass
    def makeList(self):
        return ''.join(chr(val) for val in [126, 6, 25, 0, 0] + self.show.makeList() + [231])

class MainView(object):
    """The view for the stage itself"""
    def __init__(self, structure, show):
        self.structure = structure
        self.show = show
        self.stageImage = pygame.image.load('stage.png').convert_alpha()
        self.font = pygame.font.Font(None, 20)
    def draw(self):
        screen.blit(self.stageImage, (0, 0))
        img = self.font.render(str(self.show.currentPage.idno),
                               0, (255, 0, 0))
        yield screen.blit(img, (3, 3))
        lights = self.show.getLights()
        for pos, radius, name in self.structure:
            rect = pygame.draw.circle(screen, (255 * lights[name] / 100,
                                               255 * lights[name] / 100,
                                               0),
                                      pos, radius)
            img = self.font.render(name, 0, (255, 0, 0))
            screen.blit(img, (pos[0] - img.get_width() / 2, pos[1]))
            yield rect
    getName = lambda self, pos: self.structure.getName(pos)

class PreviewModel(object):
    """The model for the preview pages"""
    def __init__(self, show, idFunction):
        self.show = show
        self.idFunction = idFunction
        self.depth = 0
    def getID(self):
        retId = self.idFunction(self.show.currentPage)
        link = 'previous' if (self.depth < 0) else 'next'
        depth = self.depth
        newId = retId
        while depth != 0:
            try:
                newId = self.show.pages[newId].links[link]
            except KeyError:
                return retId
            if newId == -1:
                return retId
            depth += 1 if (self.depth < 0) else -1
            retId = newId
        return retId
    getLights = lambda self: self.show.getPreview(self.getID())
    def toggleIntensity(self, name):
        self.show.toggleIntensity(name, self.getID())
    def turnOff(self, name):
        self.show.turnOff(name, self.getID())
    def adjustDepth(self, diff):
        self.depth += diff
    def resetDepth(self):
        self.depth = 0
    def setNext(self):
        self.show.setNext(self.getID())

class PreView(object):
    """Shows a preview of a different page"""
    def __init__(self, model, structure, offset):
        self.structure = structure
        self.model = model
        self.offset = offset
        self.stageImage = pygame.image.load('stage.png').convert_alpha()
        self.stageImage = pygame.transform.scale(self.stageImage, (160, 120))
        self.font = pygame.font.Font(None, 5)
        self.largeFont = pygame.font.Font(None, 20)
    def draw(self):
        screen.blit(self.stageImage, self.offset)
        img = self.largeFont.render(str(self.model.getID())[:2], 0, (255, 0, 0))
        yield screen.blit(img, (self.offset[0] + 3,
                                self.offset[1] + 3))
        lights = self.model.getLights()
        for pos, radius, name in self.structure:
            pos = (self.offset[0] + pos[0] / 3,
                   self.offset[1] + pos[1] / 3)
            rect = pygame.draw.circle(screen, (255 * lights[name] / 100,
                                               255 * lights[name] / 100,
                                               0),
                                      pos, radius / 3)
            img = self.font.render(name, 0, (255, 0, 0))
            screen.blit(img, (pos[0] - img.get_width() / 2, pos[1]))
            yield rect
        yield screen.fill((100, 100, 100), pygame.Rect(self.offset, (160, 2)))
    def getName(self, pos):
        """Converts a mouse click into the corresponding light"""
        pos = tuple((pos[i] - self.offset[i]) * 3 for i in xrange(2))
        return self.structure.getName(pos)

class PreviewController(Controller):
    """Used to handle events relating to the preview page"""
    def __init__(self, view, show, macros, output):
        Controller.__init__(self, view, show, macros, output)
        self.keyActions = (Action(lambda event: event.key == pygame.K_n,
                                  lambda: show.adjustDepth(1)),
                           Action(lambda event: event.key == pygame.K_p,
                                  lambda: show.adjustDepth(-1)),
                           Action(lambda event: event.key == pygame.K_PAGEUP,
                                  show.resetDepth),
                           Action(lambda event: event.key == pygame.K_PAGEDOWN,
                                  show.resetDepth),
                           Action(lambda event: event.key == pygame.K_s,
                                  show.setNext))
    
font = pygame.font.Font(None, 20)

class NoteView(object):
    """Used to deal with the notes of each cue"""
    def __init__(self, show, offset):
        self.offset = offset
        self.show = show
    def draw(self):
        yield screen.fill((100, 100, 100), pygame.Rect(self.offset, (160, 2)))
        if self.show.currentPage.notes:
            img = font.render(self.show.currentPage.notes, 0, (255, 255, 255))
            yield screen.blit(img, (self.offset[0], self.offset[1] + 20))

class NoteController(object):
    """Used to deal with the notes"""
    def __init__(self, show, offset):
        self.offset = offset
        self.show = show
        self.updating = False
    def updateEvents(self, getEvents):
        for event in getEvents():
            if event.type == pygame.MOUSEBUTTONDOWN:
                if all(self.offset[i] < event.pos[i] < self.offset[i] + 160
                       for i in xrange(2)):
                    self.updating = True
                    self.show.currentPage.notes = ''
                else:
                    self.updating = False
            elif event.type == pygame.KEYDOWN:
                if self.updating:
                    if len(event.unicode) == 0:
                        return
                    if ord(event.unicode) == 8:
                        #backspace
                        self.show.currentPage.notes = self.show.currentPage.notes[:-1]
                    else:
                        self.show.currentPage.notes += event.unicode


class MockOutput(object):
    def write(self, _): pass
    def isOpen(self): return ''

def main():
    from sys import argv
    channelList = (('CC', 0),
                   ('CIR', 1),
                   ('CSL', 2),
                   ('BackHals', 3),
                   ('FC', 4),
                   ('FIL', 5),
                   ('FSR', 6),
                   ('FSL', 7),
                   ('BC', 8),
                   ('BSR', 9),
                   ('BSL', 9),
                   ('ONHALS', 10),
                   ('TRACKS', 11),
                   ('FCOFF', 12),
                   ('RS', 14),
                   ('RAMP', 14),
                   ('RC', 15),
                   ('FCOFF', 13),
                   ('OFFHALS', 16),
                   ('CC', 18),
                   ('CIL', 19),
                   ('CSR', 20),
                   ('FC', 22),
                   ('FIR', 23))
    try:
        show = argv[1]
    except IndexError:
        show = 'noshow'
    show = Show(show, channelList)
    
    try:
        structure = argv[2]
    except IndexError:
        structure = 'basicStructure.lst'
    try:
        running = (argv[3].lower() != 'false')
    except IndexError:
        running = True
    port = serial.Serial('COM26') if running else MockOutput()
    structure = LightStructure(structure)
    macros = MacroRecorder()
    mainView = MainView(structure, show)
    controller = MainController(structure, show, macros, port)
    macros.setRefreshOutput(controller.refreshOutput)
    controller.setRunning(running)
    nextPageModel = PreviewModel(show,
                                 lambda currentPage : currentPage.links['next'])
    nextPageView = PreView(nextPageModel, structure, (480, 0))
    nextPageController = PreviewController(nextPageView, nextPageModel,
                                           macros, MockOutput())
    interruptPageModel = PreviewModel(show, lambda _ : 'interrupt')
    interruptPageView = PreView(interruptPageModel, structure, (480, 160))
    interruptController = Controller(interruptPageView, interruptPageModel,
                                     macros, MockOutput())
    noteView = NoteView(show, (480, 320))
    noteController = NoteController(show, (480, 320))
    wrapper = EventWrapper()
    #Keep the main controller after the preview controllers.
    #Keep the note controller last
    controllers = [nextPageController, interruptController, controller,
                   macros, noteController]
    views = [mainView, nextPageView, interruptPageView, noteView]
    while wrapper.keepRunning:
        wrapper.refreshEvents()
        for controller in [noteController] if noteController.updating else controllers:
            controller.updateEvents(wrapper.getEvents)
        screen.fill((0, 0, 0))
        for view in views:
            list(view.draw())
        screen.fill((100, 100, 100), pygame.Rect(478, 0, 4, 480))
        pygame.display.flip()

if __name__ == '__main__':
    stackless.tasklet(main)()
    stackless.run()
 
