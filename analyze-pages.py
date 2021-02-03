import csv
import re
import os
import bz2
import cPickle
import sys
from collections import namedtuple, defaultdict
from datetime import datetime
from pprint import pprint

TestRecord = namedtuple('TestRecord', 'testID tester machine cpu mhz hwAvail os compiler autoParallel benchType base peak')
BenchRecord = namedtuple('BenchRecord', 'testID benchName base peak')

def scanUntilLine(lineIter, pattern):
    for line in lineIter:
        m = re.search(pattern, line)
        if m:
            g = m.groups()
            if len(g) == 1:
                return g[0].strip()            
            return [x.strip() for x in g]

MHzExp = re.compile('[(/]?(\\d+(?:\\.\\d+)?)a? ?([mg]hz)\\)?')

def ExtractMHzFromName(name):
    name = name.lower()
    m = MHzExp.search(name)
    value, units = m.groups()
    value = float(value)
    if units == 'ghz':
        value *= 1000
    return value

def parse95(path):
    testID = os.path.splitext(os.path.basename(path))[0]    
    lineIter = iter(open(path))
    for line in lineIter:
        if line.startswith('   ------------  --------  --------  --------  --------  --------  --------'):
            break
        if 'SPEC has determined that this result was not in' in line:
            return [], []
    benches = []
    for line in lineIter:
        m = re.match('   (SPEC.{32}) ', line)
        if m:
            benchType = m.group(1).strip()
            break
        benchName = line[:15].strip()
        base = line[35:45].strip()
        peak = line[65:75].strip()
        benches.append(BenchRecord(testID, benchName, base, peak))
    if '_rate' in benchType:
        return [], []
    benchType = {
        'SPECint_base95 (Geom. Mean)' : 'CINT95',
        'SPECfp_base95 (Geom. Mean)' : 'CFP95'
    }[benchType]
    base = line[35:45].strip()
    peak = lineIter.next()[65:75].strip()
    properties = {}
    label = ''
    for line in lineIter:
        l = line.strip()
        if l in ['HARDWARE', 'SOFTWARE', 'TESTER INFORMATION', '------------------', '--------']:
            continue
        if l == 'NOTES':
            break
        if line[19:20] == ':':
            label = line[:19].strip()
        desc = line[21:].strip()
        if label and desc:
            if label in properties:
                properties[label] += ' ' + desc
            else:
                properties[label] = desc
    cpu = properties['CPU']
    mhz = ExtractMHzFromName(cpu)
    opSys = properties['Operating System']
    compiler = properties['Compiler']
    if 'Hardware Avail' not in properties:
        html = open(path[:-4] + '.html').read()
        m = re.search('Hardware Avail:\\s+<TD align=left>([^\\s]+)\\s', html)
        hwAvail = m.group(1).strip()
        m = re.search('Tested By:\\s+<TD align=left>(.+)$', html, re.MULTILINE)
        testedBy = m.group(1).strip()
    else:
        hwAvail = properties['Hardware Avail']
        testedBy = properties['Tested By']
    try:
        hwAvail = datetime.strptime(hwAvail, '%b-%y').strftime('%b-%Y')
    except ValueError:
        pass
    model = properties['Model Name']
    
    testRecord = TestRecord(testID, testedBy, model, cpu, mhz, hwAvail, opSys, compiler, 'No', benchType, base, peak)
    return [testRecord], benches


def parse2000(path):
    testID = os.path.splitext(os.path.basename(path))[0]    
    lineIter = iter(open(path))
    lineIter.next()
    hwAvail = scanUntilLine(lineIter, 'Hardware availability: (.*)')
    tester = scanUntilLine(lineIter, 'Tester: (.*?) *Software availability')
    for line in lineIter:
        if line.startswith('   ========================================================================'):
            break
        if 'SPEC has determined that this result was not in' in line:
            return [], []
    benches = []
    for line in lineIter:
        m = re.match('   (SPEC.{24})    ', line)
        if m:
            benchType = m.group(1).strip()
            break
        benchName = line[:15].strip()
        base = line[35:45].strip()
        peak = line[65:75].strip()
        benches.append(BenchRecord(testID, benchName, base, peak))
    if '_rate_' in benchType:
        return [], []
    benchType = {
        'SPECint_base2000' : 'CINT2000',
        'SPECfp_base2000' : 'CFP2000'
    }[benchType]
    base = line[35:45].strip()
    peak = lineIter.next()[65:75].strip()
    properties = {}
    label = ''
    for line in lineIter:
        l = line.strip()
        if l in ['HARDWARE', 'SOFTWARE', '--------']:
            continue
        if l == 'NOTES':
            break
        if line[20:21] == ':':
            label = line[:20].strip()
        desc = line[22:].strip()
        if label and desc:
            if label in properties:
                properties[label] += ' ' + desc
            else:
                properties[label] = desc
    cpu = properties['CPU']
    mhz = float(properties['CPU MHz'])
    opSys = properties['Operating System']
    compiler = properties['Compiler']
    model = properties['Model Name']
    
    testRecord = TestRecord(testID, tester, model, cpu, mhz, hwAvail, opSys, compiler, 'No', benchType, base, peak)
    return [testRecord], benches


def parse2006(path):
    testID = os.path.splitext(os.path.basename(path))[0]    
    lineIter = iter(open(path))
    if '######################' in lineIter.next():
        return [], []
    model = lineIter.next().strip()
    hwAvail = scanUntilLine(lineIter, 'Hardware availability: (.*)')
    tester = scanUntilLine(lineIter, 'Tested by:    (.*?) *Software availability')
    if model.startswith(tester):
        model = model[len(tester):].strip()
    for line in lineIter:
        if line.startswith('=============================================================================='):
            break
        if 'SPEC has determined that this result was not in' in line:
            return [], []
        if 'SPEC has determined that this result is not in' in line:
            return [], []
    benches = []
    for line in lineIter:
        m = re.match(' (SPEC.{27})  ', line)
        if m:
            benchType = m.group(1).strip()
            break
        benchName = line[:15].strip()
        base = line[30:35].strip()
        peak = line[35:46].strip()
        benches.append(BenchRecord(testID, benchName, base, peak))
    if '_rate_' in benchType:
        return [], []
    benchType = {
        'SPECint(R)_base2006' : 'CINT2006',
        'SPECfp(R)_base2006' : 'CFP2006',
        'SPECint(R)_rate_base2006' : 'CINT2006',
        'SPECfp(R)_rate_base2006' : 'CFP2006'
    }[benchType]
    base = line[33:].strip()
    peak = lineIter.next()[65:].strip()
    properties = {}
    label = ''
    for line in lineIter:
        l = line.strip()
        if l in ['HARDWARE', 'SOFTWARE', '--------']:
            continue
        if l == 'Submit Notes':
            break
        if line[20:21] == ':':
            label = line[:20].strip()
        desc = line[22:].strip()
        if label and desc:
            if label in properties:
                properties[label] += ' ' + desc
            else:
                properties[label] = desc
    cpu = properties['CPU Name']
    mhz = float(properties['CPU MHz'])
    opSys = properties['Operating System']
    compiler = properties['Compiler']
    autoParallel = properties['Auto Parallel']
    
    testRecord = TestRecord(testID, tester, model, cpu, mhz, hwAvail, opSys, compiler, autoParallel, benchType, base, peak)
    return [testRecord], benches

def parse2017(path):
    testID = os.path.splitext(os.path.basename(path))[0]    
    lineIter = iter(open(path))
    if '######################' in lineIter.next():
        return [], []
    model = lineIter.next().strip()
    hwAvail = scanUntilLine(lineIter, 'Hardware availability: (.*)')
    tester = scanUntilLine(lineIter, 'Tested by:    (.*?) *Software availability')
    if model.startswith(tester):
        model = model[len(tester):].strip()
    for line in lineIter:
        if line.startswith('=============================================================================='):
            break
        if 'SPEC has determined that this result was not in' in line:
            return [], []
        if 'SPEC has determined that this result is not in' in line:
            return [], []
    benches = []
    bench2 = []
    for line in lineIter:
        m = re.match(' (SPEC.{27})  ', line)
        if m:
            benchType = m.group(1).strip()
            break
        benchName = line[:15].strip()
        base = line[25:35].strip()
        peak = line[36:46].strip()
        bench2.append(BenchRecord(testID, benchName, base, peak))
        benches.append(BenchRecord(testID, benchName, base, peak))
    if '_rate_' in benchType:
        return [], []
    benchType = {
        'SPECint2017_int_base' : 'CINT2017',
        'SPECfp2017_fp_base' : 'CFP2017',
        'SPECrate2017_int_base' : 'CINT2017',
        'SPECrate2017_fp_base' : 'CFP2017',
        'SPECint(R)2017_int_base' : 'CINT2017',
        'SPECfp(R)2017_fp_base' : 'CFP2017',
        'SPECrate(R)2017_int_base' : 'CINT2017',
        'SPECrate(R)2017_fp_base' : 'CFP2017',
        'SPECint2017(R)_int_base' : 'CINT2017',
        'SPECfp2017(R)_fp_base' : 'CFP2017',
        'SPECrate2017(R)_int_base' : 'CINT2017',
        'SPECrate2017(R)_fp_base' : 'CFP2017',
        'SPECspeed2017(R)_int_base' : 'CINT2017',
        'SPECspeed2017(R)_fp_base' : 'CFP2017',
    }[benchType]
    base = line[33:43].strip()
    peak = lineIter.next()[65:75].strip()
    properties = {}
    label = ''
    for line in lineIter:
        l = line.strip()
        if l in ['HARDWARE', 'SOFTWARE', '--------']:
            continue
        if l == 'Submit Notes':
            break
        if line[20:21] == ':':
            label = line[:20].strip()
        desc = line[22:].strip()
        if label and desc:
            if label in properties:
                properties[label] += ' ' + desc
            else:
                properties[label] = desc
    cpu = properties['CPU Name']
    if 'Max MHz' in properties:
        mhz = float(properties['Max MHz'])
    else:
        mhz = float(properties['Max MHz.'])
    opSys = properties['OS']
    compiler = properties['Compiler']
    autoParallel = properties['Parallel']
    
    testRecord = TestRecord(testID, tester, model, cpu, mhz, hwAvail, opSys, compiler, autoParallel, benchType, base, peak)
    return [testRecord], benches

def iterRecords():
    allTests = []
    
    for fn in os.listdir(os.path.join('scraped', 'cpu95')):
        if fn.lower().endswith('.asc'):
            allTests.append((parse95, os.path.join('scraped', 'cpu95', fn)))
    for fn in os.listdir(os.path.join('scraped', 'cpu2000')):
        allTests.append((parse2000, os.path.join('scraped', 'cpu2000', fn)))
    for fn in os.listdir(os.path.join('scraped', 'cpu2006')):
        allTests.append((parse2006, os.path.join('scraped', 'cpu2006', fn)))
    for fn in os.listdir(os.path.join('scraped', 'cpu2017')):
        allTests.append((parse2017, os.path.join('scraped', 'cpu2017', fn)))
    
    tests = []
    benches = []
    for i, pair in enumerate(allTests):
        if i % 100 == 0:
            print 'Analyzing %d/%d ...' % (i, len(allTests))
        try:
            func, arg = pair
            t, b = func(arg)
            tests += t
            benches += b
        except:
            print 'Error on '+arg
            
    print 'Writing summaries.txt ...'
    with open('summaries.txt', 'w') as f:
        w = csv.writer(f)
        w.writerow(TestRecord._fields)
        for t in tests:
            w.writerow(t)
            
    print 'Writing benchmarks.txt ...'
    with open('benchmarks.txt', 'w') as f:
        w = csv.writer(f)
        w.writerow(BenchRecord._fields)
        for b in benches:
            w.writerow(b)
            
iterRecords()
