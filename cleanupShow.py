"""When shows are made with the old stage and then compiled, use this to
remove synonyms"""
import sys
import json

def cleanSingle(page, primaries, names):
    try:
        for primary in primaries:
            page['lights'][primary] = max(page['lights'][name] for name in names)
        for name in names:
            if name not in primaries:
                del page['lights'][name]
    except KeyError:
        pass
    
def cleanup(page):
    cleanSingle(page, 'ONHALS', ('ONHALS', 'ONSTAGE'))
    cleanSingle(page, 'OFFHALS', ('OFFSTAGE', 'OFFHALS'))
    cleanSingle(page, 'CC', ('CC', 'SCC', 'WCC'))
    cleanSingle(page, ('RS', 'RC'), ('RS', 'RC', 'RAMP'))
    return page

def main(fileName):
    with open(fileName) as fil:
        newPages = [cleanup(page) for page in json.loads(fil.read())]

    with open(fileName, 'w') as fil:
        fil.write(json.dumps(newPages, indent=1))

if __name__ == '__main__':
    main(sys.argv[1])
