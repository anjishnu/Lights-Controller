def readLights(fileName):
    names = []
    with open(fileName + '.shw') as fil:
        for lin in fil.xreadlines():
            values = lin.split(',')
            values = [value[1:-1] for value in values]
            if 'Demonstration' in values[0]:
                continue
            else:
                try:
                    num = int(float(values[0]))
                    lights = ((name, int(values[i+1])) for i, name
                              in enumerate(names))
                    yield num, lights
                except ValueError:
                    names = values

def makeCLT(fileName, pages):
    with open(fileName + '.clt', 'w') as fil:
        for num, lights in pages:
            if num == 0:
                continue
            fil.write('Page %s\n'%(num))
            for name, value in lights:
                if value is not 0:
                    fil.write('%s: %s\n'%(name, value))
            fil.write('\n')

def main(fileName):
    makeCLT(fileName, readLights(fileName))

if __name__ == '__main__':
    import sys
    main(sys.argv[1])
