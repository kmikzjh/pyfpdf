#!/usr/bin/env python
# -*- coding: utf-8 -*-

import cover
import fpdf

import sys, os, shutil
import traceback
import subprocess

def search_python_posix():
    lst = []
    path = os.environ.get("PATH")
    for item in path.split(":"):
        for interp in os.listdir(item):
            if interp[:6] != "python":
                continue
            if interp[-7:] == "-config":
                continue
            fp = os.path.join(item, interp)
            # test if already in list
            same = False
            for lidx, l_interp in enumerate(lst):
                if os.path.samefile(l_interp, fp):
                    same = True
                    # use shorter name
                    if len(l_interp) < len(fp):
                        lst[lidx] = fp
                    break
            if same:
                continue
            lst.append(fp)
    return lst
           
def search_python_win():
    lst = []
    try:
        try:
            import _winreg as winreg
        except ImportError:
            import winreg
        def findreg(key, lst):
            PATH = "SOFTWARE\\Python\\PythonCore"
            try:
                rl = winreg.OpenKey(key, PATH)
            except WindowsError:
                return lst
            try:
                for i in range(winreg.QueryInfoKey(rl)[0]):
                    ver = winreg.EnumKey(rl, i)
                    rv = winreg.QueryValue(key, PATH + "\\" + ver + "\\InstallPath")
                    fp = os.path.join(rv, "python.exe")
                    #print fp
                    if os.path.exists(fp) and not fp in lst:
                        lst.append(fp)
            except WindowsError:
                pass
            return lst
        lst = findreg(winreg.HKEY_LOCAL_MACHINE, lst)
        lst = findreg(winreg.HKEY_CURRENT_USER, lst)
    except:
        traceback.print_exc()
        # fallback
        cover.log("Search python at system drive")
        try:
            path = os.environ.get("SystemDrive", "C:")
            for item in os.listdir(path):
                if item[:6].lower() != "python":
                    continue
                fp = os.path.join(path, item, "python.exe")
                if os.path.exists(fp) and not fp in lst:
                    lst.append(fp)
        except:
            traceback.print_exc()
        
    return lst

def search_python():
    if sys.platform.startswith("linux"):
        lst = search_python_posix()
    elif sys.platform.startswith("win"):
        lst = search_python_win()
    else:
        lst = search_python_posix()
    if len(lst) == 0:
        # fallback
        lst.append(sys.executable)
    return lst

def find_python_version(pylst):
    lst = []
    ids = []
    for interp in pylst:
        try:
            std, err = cover.execcmd([interp, "-V"])
            version = err.strip()
            if version[:6] == "Python":
                shver = version[6:].strip().replace(" ", "-")
                nid = shver
                nidn = 0
                while nid in ids:
                    nidn += 1
                    nid = shver + "-%d" % nidn
                ids.append(nid)
                lst.append((interp, nid, version))
            else:
                cover.err("Not a python", version)
                # no python found
                continue
        except:
            traceback.print_exc()
    return lst

def search_tests():
    base = os.path.join(cover.basepath, "cover")
    lst = []
    for item in os.listdir(base):
        if item[:5] != "test_":
            continue
        lst.append(os.path.join(base, item))
    lst.sort()
    return lst

def dotestone(testfile, interp, info, dest):
    path = interp[0]
    nid = interp[1]
    tool2to3 = (info.get("2to3", "no") == "yes")
    py2 = (info.get("python2", "yes") == "yes")
    py3 = (info.get("python3", "yes") == "yes")
    testname = os.path.basename(testfile)
    testfmt = info.get("format", "raw")
    copy = False
    if nid[:2] == "3.":
        if not py3:
            return "skip"
        if not tool2to3:
            copy = True
        else:
            return "unimplemented"
    if nid[:2] == "2.":
        if not py2:
            return "skip"
        copy = True
    # copy files
    newfile = os.path.join(dest, testname)
    newres = os.path.join(dest, info.get("fn", testname + "." + testfmt.lower()))
    if copy:
        shutil.copy(testfile, dest)
    # start execution
    std, err = cover.execcmd([path, "-B", newfile, "--check", "--auto", newres])
    f = open(os.path.join(dest, "testlog.txt"), "a")
    f.write("#" * 40 + "\n")
    f.write(testname + "\n")    
    f.write("=" * 40 + "\n")
    f.write(std)    
    f.write("-" * 40 + "\n")
    f.write(err)
    f.close()
    
    answ = std.strip()
    if answ.find("\n") >= 0 or len(answ) == 0:
        return "fail"
    else:
        return answ.lower()
    #print "="*40
    #print std
    #print "-"*40
    #print err
    #print "="*40

def preparedest(interp):
    dest = os.path.join(cover.basepath, "out-" + interp[1])
    if not os.path.exists(dest):
        os.makedirs(dest)
    # copy common set
    src = os.path.join(cover.basepath, "cover")
    shutil.copy(os.path.join(src, "__init__.py"), dest)
    shutil.copy(os.path.join(src, "common.py"), dest)
    f = open(os.path.join(dest, "testlog.txt"), "w")
    f.write("Version: " + interp[1] + "\n")
    f.write("Path: " + interp[0] + "\n")
    f.write(str(interp[2:]) + "\n")
    f.close()
    
    return dest

def dotest(testfile, interps, dests, stats, hint = ""):
    cover.log("Test", hint, ":", os.path.basename(testfile))
    info = cover.readcoverinfo(testfile)
    resall = ""       
    # prepare
    # do tests
    for interp in interps:
        if len(interps) < 6:
            resall += (interp[1] + " - ")
        res = dotestone(testfile, interp, info, dests[interp[1]])
        # update statistic
        stats["_"]["_"] += 1
        stats["_"][res] = stats["_"].get(res, 0) + 1
        stats[interp[1]]["_"] += 1
        stats[interp[1]][res] = stats[interp[1]].get(res, 0) + 1
        resall += (res + " " * 4)[:4].upper()
        resall += "  "
    cover.log(resall)


def doalltest(interps):
    cover.log(">> Interpretators:", len(interps))
    dests = {}
    stats = {"_": {"_": 0}}
    for idx, interp in enumerate(interps):
        cover.log("%d) %s - %s" % (idx + 1, interp[1], interp[0]))
        dests[interp[1]] = preparedest(interp)
        stats[interp[1]] = {"_": 0}
    cover.log()
    tst = search_tests()

    cover.log(">> Tests:", len(tst))
    for idx, test in enumerate(tst):
        dotest(test, interps, dests, stats, "%d / %d" % (idx + 1, len(tst)))
    cover.log()

    cover.log(">> Statistics:")
    def statstr(stat):
        keys = stat.keys()
        keys.sort()
        st = "total - %d" % stat["_"]
        for key in keys:
            if key == "_":
                continue
            st += (", %s - %d" % (key, stat[key]))
            
        return st
    for interp in interps:
        cover.log(interp[1] + ":", statstr(stats[interp[1]]))
    cover.log("-"*10)
    cover.log("All:", statstr(stats["_"]))

def usage():
    cover.log("Usage: todo")

def main():
    cover.log("Test FPDF", fpdf.FPDF_VERSION)
    ins = find_python_version(search_python())
    #if len(sys.argv) == 1:
    #    return usage()
    doalltest(ins)
    
    
if __name__ == "__main__":
    main()