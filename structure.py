"""Used to setup the positions of lights on the stage"""

import stackless
import pygame
pygame.init()

import csv

screen = pygame.display.set_mode((640, 480))

def chkCircle(center, radius, point):
    return sum((center[i] - point[i])**2 for i in xrange(2)) < radius ** 2

class LightStructure(object):
    """The class for the structure of lights"""
    #SoA vs AoS. I think that it works better here. Too much JS programming.
    def __init__(self, fileName):
        self.pos = []
        self.radius = []
        self.names = []
        self._fileName = fileName
        try:
            fil = open(fileName)
            reader = csv.reader(fil)
            for x, y, radius, name in reader:
                self.pos.append((int(x), int(y)))
                self.radius.append(int(radius))
                self.names.append(name)
        except IOError:
            pass
        self.highlighted = -1
    def getPointIndices(self, point):
        return (i for i, (pos, radius) in
                enumerate(zip(self.pos, self.radius))
                if chkCircle(pos, radius, point))
    def deleteIndices(self, indices):
        """Removes a set of lights from the structure"""
        indices = list(indices)
        for i in indices[::-1]:
            del self.pos[i]
            del self.radius[i]
            del self.names[i]
    def save(self):
        fil = open(self._fileName, 'w')
        writer = csv.writer(fil)
        writer.writerows((pos[0], pos[1], radius, name) for pos, radius, name
                         in zip(self.pos, self.radius, self.names))
        fil.close()
    def getName(self, pos):
        try:
            return self.names[list(self.getPointIndices(pos))[0]]
        except IndexError:
            return False
    def append(self, pos):
        self.pos.append(pos)
        self.radius.append(35)
        nameIndex = len(self.names)
        name = 'Light %d'%(nameIndex)
        while name in self.names:
            nameIndex += 1
            name = 'Light %d'%(nameIndex)
        self.names.append(name)
        self.highlighted = len(self.pos) - 1
    def replaceName(self, name):
        self.names[self.highlighted] = name
    def __iter__(self):
        return zip(self.pos, self.radius, self.names).__iter__()

class StructureView(object):
    def __init__(self, structure):
        self.structure = structure
        self.stageImage = pygame.image.load('stage.png').convert_alpha()
        self.font = pygame.font.Font(None, 20)
    def draw(self):
        """Draws all the lights on the screen"""
        screen.blit(self.stageImage, (0, 0))
        for i, (pos, radius, name) in enumerate(self.structure):
            rect = pygame.draw.circle(screen, (255, 255, 0), pos, radius)
            if i == self.structure.highlighted:
                pygame.draw.circle(screen, (255, 0, 0), pos, radius, 2)
            img = self.font.render(name, 0, (255, 0, 0), (255, 255, 0))
            screen.blit(img, (pos[0] - img.get_width() / 2, pos[1]))
            yield rect

class StructureController(object):
    def __init__(self, structure):
        self.structure = structure
        self.editing = False
    def updateEvents(self, getEvents):
        """Updates the lights with events"""
        for event in getEvents():
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.pos[1] > 480:
                    continue
                if event.button == 1:
                    self.editing = False
                    try:
                        self.structure.highlighted = list(self.structure.getPointIndices(event.pos))[0]
                    except IndexError:
                        self.structure.append(event.pos)
                elif event.button == 3:
                    indices = self.structure.getPointIndices(event.pos)
                    self.structure.deleteIndices(indices)
            elif event.type == pygame.KEYDOWN:
                if ('a' <= str(event.unicode) <= 'z' or
                    'A' <= str(event.unicode) <= 'Z'):
                    if self.structure.highlighted == -1:
                        continue
                    if not self.editing:
                        self.editing = True
                        newName = ''
                    else:
                        newName = self.structure.names[self.structure.highlighted]
                    newName += event.unicode
                    self.structure.replaceName(newName)
                elif event.key == pygame.K_RETURN:
                    self.structure.highlighted = -1
                    self.editing = False
                elif event.unicode == u'':
                    self.structure.save()


class EventWrapper(object):
    def __init__(self):
        self.keepRunning = True
        self.events = []
    def getEvents(self):
        return self.events
    def refreshEvents(self):
        self.events = []
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.keepRunning = False
                break
            else:
                self.events.append(event)

def main():
    from sys import argv
    try:
        lights = LightStructure(argv[1])
    except IndexError:
        lights = LightStructure('basicStructure.lst')
    lightsView = StructureView(lights)
    structureController = StructureController(lights)
    wrapper = EventWrapper()
    while wrapper.keepRunning:
        wrapper.refreshEvents()
        structureController.updateEvents(wrapper.getEvents)
        screen.fill((0, 0, 0), pygame.Rect(0, 0, 480, 480))
        screen.fill((200, 200, 200), pygame.Rect(480, 0, 160, 480))
        list(lightsView.draw())
        pygame.display.flip()

if __name__ == '__main__':
    stackless.tasklet(main)()
    stackless.run()
    
