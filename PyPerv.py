#!/usr/bin/env python
# -*- coding: utf-8 -*-

# I don't have any rights over the content downloaded with this software
# Belongs to its owners

# this software is under the terms of the gnu GPL license

#@ make output manager with curses

import urllib, urllib2, socket
import os, sys, time, threading, Queue
import zipfile, tempfile, shutil
import io, gzip, re, random, string

try:
    import lxml.etree as ET
except ImportError:
    print 'You must install lxml lib\ntry on pypi.org !'
    raise SystemExit

try:
    import socks
except ImportError:
    PY_SOCKS = False
else:
    PY_SOCKS = True

headers = {"User-Agent": """Mozilla/5.0 (X11; L; Linux i686; en-US)
                    AppleWebKit/534.3 (KHTML, like Gecko)
                    Chrome/6.0.472.14 Safari/534.3""", "Accept": """text/html,
                    application/xhtml+xml,
                    application/xml;q=0.9,*/*;q=0.8""",
                     'Accept-Encoding': 'gzip'}

# this class belongs to helper classes section
class Memo:
    """memorizer for mangaList because we don't want to use unnecessary
         bandwidth """

    def __init__(self, func):
        self.func = func
        self.list = []

    def __call__(self):
        if self.list:
            return self.list
        else:
            self.list = self.func()
            return self.list

#! this function needs to be fixed
def parseInput():
    if (len(sys.argv) != 2):
        manga = raw_input("what manga you meant enter it again: ")
        manga = manga.lstrip()
        print "\n"
    elif len(sys.argv) == 2:
        manga = sys.argv[1]

    getList()
    return manga


@Memo
def getList():
    try:
        html = getSource('http://fufufuu.net/tanks/', headers)
    except urllib2.URLError:
        print "No internet connection !"
        raise SystemExit

    mangaElements = xpathSearch(html, '//li[@class="tli"]/a')
    mangalist = []
    for elem in mangaElements:
        mangalist.append((elem.getchildren()[0].text, elem.attrib.get('href')))
    return mangalist


def searchForManga(keyWord):
    resultList = []
    mainURL = 'http://fufufuu.net/search?'
    parKwd = urllib.urlencode({'q': keyWord})
    while True:
        try:
            page = getSource(mainURL + parKwd, headers)
            aElms = xpathSearch(page, '//li[@class="mli"]/a')
            pElms = xpathSearch(page, '//li[@class="mli"]/p')
        except urllib2.URLError:
            print 'Connection Lost !!!'
            raise SystemExit
        except NotFound:
            pass
        else:
            break

    for elm in pElms:
        resultList.append(
            (elm.text, aElms[pElms.index(elm)].attrib.get('href')))
    selectMangaAndChapters(resultList)


def selectMangaAndChapters(sResult=None):
    target = None
    if not sResult:
        rawManga = parseInput()
        mangaList = getList()
    else:
        rawManga = 'all'
        mangaList = sResult

    if rawManga.lower() == 'all':
            for manga in mangaList:
                print "%i) %s" % (mangaList.index(manga) + 1, manga[0])
            question = "\nPlease type the manga index: "
            while True:
                try:
                    target = askSelect(question, mangaList)
                except ValueError:
                    print "unexcepicted value"
                    continue
                else:
                    if sResult:
                        downloadChapter(target[0], target[0], target[1])
                        raise SystemExit
                    break
    else:
        miniList = []
        for mangaOnline in mangaList:
            if rawManga.lower() == mangaOnline[0].lower():
                target = mangaOnline
                break
            elif findInStr(rawManga, mangaOnline[0]):
                    miniList.append(mangaOnline)

    if not target:
        if miniList:
            for manga in miniList:
                print '%i) %s' % (miniList.index(manga) + 1, manga[0])
            print "\nI couldn't find your manga So !"
            print "those are some kind similar"
            while True:
                question = "\nPlease type the manga index: "
                try:
                    target = askSelect(question, miniList)
                except ValueError:
                    question = "\nDo you want to try more tought search y\\n ? "
                    ans = askSelect(question, ansList=['y','n'], equOpsFunction=str.lower)
                    if ans == 'y':
                        break
                    else:
                        continue
                else:
                    break
        else:
            print 'No similar manga !!!\nLets try with the site search :)'

    if target:
        link = target[1]
        while True:
            try:
                page = getSource('http://fufufuu.net%s' % link, headers)
                chapterElements = xpathSearch(page, '//li[@class="mli"]/a');chapterElements.reverse()
                chapterNames = xpathSearch(page, '//p[@class="mli-title"]');chapterNames.reverse()
            except (urllib2.URLError):
                print '\nConnection lost !!!'
                raise SystemExit
            except NotFound:
                pass
            else:
                break
        for chapterName in chapterNames :
            print "%i) %s" % (chapterNames.index(chapterName) + 1, chapterName.text)
        while True:
            question = '\nPlease type the number of chapter(s) you want separate with a space or ,: '
            genObj = askSelect(question, chapterElements, multiChoice=True)
            for ch in genObj:
                link = ch.get('href')
                name = link.split('/')[-2]
                downloadChapter(target[0], name, link)
    else:
        searchForManga(rawManga)

#! add threads for multi chapter download


def downloadChapter(mangaName, name, link):
    patPages = re.compile('\d{1,3}')
    while True:
        try:
            mainPage = getSource('http://fufufuu.net/%s' % link, headers)
            pages = int(re.search(
            patPages, xpathSearch(mainPage, "//span[@class='text-small']", 'find').text).group())
            patLinks = re.compile('/media/p/\w{1,3}/\w{1,3}/\w+.\w{3}')
            imgLinks = re.findall(patLinks, xpathSearch(mainPage, '//div[@id="payload"]', 'find').text)
        except urllib2.URLError:
            print "Connection lost !!!"
            raise SystemExit
        except NotFound:
            pass
        else:
            break

    tempDir = tempfile.mkdtemp()
    imgPool = Queue.Queue(2)
    try:
        for img in imgLinks:
            if isEven(imgLinks.index(img)):
                thread = ImgDownload(
                        str((imgLinks.index(img) / 2) + 1),
                             img.split('.')[-1], img, 3, headers, tempDir, imgPool)
                imgPool.put(thread)
            else:
                if (imgPool.full()) or (not imgPool.empty() and img == imgLinks[-1]):
                    imgPool.join()
                    cleanQueue(imgPool)
                    print "Progress...   %i %s" % (Percentage(
                        len(imgLinks) * 0.5, (imgLinks.index(img) + 1) * 0.5 ), '%')
        zipManga(fixformat(name), tempDir, pages)
    finally:
        cleanUp(tempDir)

#deprecated for adding thread support
#def downloadImg(name, suffix, link, tempDir):
    #while True:
        #try:
            #FURLopener(headers).retrieve(
                #'http://fufufuu.net%s' % link, os.path.join(
                    #tempDir, "%s.%s" % (name, suffix)))
        #except IOError:
            #pass
        #except urllib.ContentTooShortError as E:
            ##print E.content
            #break
        #else:
            #return True
            #break


def zipManga(name, tempDir, numPages, dist=None):
    if dist:
        if os.path.isdir(dist):
            fullPath = os.path.join(dist, name + '.cbz')
    else:
        fullPath = os.path.join(os.curdir, name + '.cbz')

    myZip = zipfile.ZipFile(fullPath, 'w')
    try:
        imgsList = os.listdir(tempDir)
    except OSError:
        print 'Temp folder deleted !!!'
        return

    print '\nCompressing.... '
    for img in imgsList:
        try:
            path = os.path.join(tempDir, img)
            if os.path.isfile(path):
                myZip.write(path, img)
            else:
                raise NotFound(path)
        except OSError:
            print 'Zip archive has been deleted !!!'
            break
        except NotFound as E:
            print "image at %s has been deleted !!!" % E.errmsg
    comment = "Manga: %s \nPages:%i\nDownloaded with PyPerv" % (name, numPages)
    myZip.comment = comment
    myZip.close()


def main():
    selectMangaAndChapters()

# ============================================================================#
#                     Helper Functions & Classes                              #
# ============================================================================#


def getSource(url, headers={}, proxy=None, maxRetrys=2, timeWait=2):
    if proxy:
        if PY_SOCKS:
            proxy = proxy.split(':')
            socks.set_default_proxy(socks.SOCKS4, proxy[0], int(proxy[1]))
            socket.socket = socks.socksocket
        else:
            print "\nCan't use proxy because pysocks is missing !?"

    socket.setdefaulttimeout(40)
    source = None
    while not source:
        try:
            request = urllib2.Request(url, headers=headers)
            respond = urllib2.urlopen(request)
            encoding = respond.headers.get('Content-Encoding')
            if not encoding:
                source = respond.read()
            elif encoding.lower() == 'gzip':
                pageBytes = io.BytesIO(respond.read())
                gzibFile = gzip.GzipFile(fileobj=pageBytes)
                source = gzibFile.read()
            else:
                raise urllib2.URLError('unknown encoding !!')
                break
        except (urllib2.URLError, IOError):
            if maxRetrys == 0:
                raise urllib2.URLError("Can't connect !!")
                break
            else:
                time.sleep(random.uniform(0.5 * timeWait, 1.5 * timeWait))
                maxRetrys -= 1

    socket.setdefaulttimeout(None)
    return source

def askSelect(question, itemList=None, multiChoice=False,
                     ansList=None, excepectedType=str, equOpsFunction = None):
    """
    get user input and test on a list of items if args (question, itemsList).
    get user input and test on a list of excepected answers if args (ansList,
    excepeetdType, eqequOpsFunction=None)
    return item from list or a genrator if the multiChoice is True.
    """
    if itemList:
        while True:
            ans = raw_input(question)
            ans = ans.replace(" ", ",").split(',')
            if multiChoice:
                def genFunc(items, indices):
                    rerun = False
                    for index in indices:
                        try:
                            yield items[int(index) - 1]
                        except (ValueError, IndexError):
                            print "\nCan't find item at index %s." % index
                            rerun = True
                    if rerun:
                        askSelect(question, itemList)
                return genFunc(itemList, ans)
            else:
                try:
                    return itemList[int(ans[0]) - 1]
                except IndexError:
                    print "Can't find item at index %s" % ans[0]
                    continue
                except:
                    raise
    elif ansList:
        if not equOpsFunction:
            equOpsFunction = excepectedType
        while True:
            ans = raw_input(question)
            try:
                for answer in ansList:
                    if answer == equOpsFunction(excepectedType(ans)):
                        return answer
                else:
                    print "didn't get this %s" % ans
                    continue
            except ValueError:
                print "thats way off %s" % ans
                continue
            else:
                break
    elif ansList and itemList:
        print 'what the heck ?'


def xpathSearch(html, xpathExp, method="findall"):
    domTree = ET.ElementTree(ET.HTML(html))
    method = getattr(domTree, method)
    result = method(xpathExp)
    if result is None:
        raise NotFound("\nCan't find element(s) by this exp %s " % xpathExp)
    else:
        return result


def cleanUp(tempDir):
    try:
        shutil.rmtree(tempDir)
    except:
        pass


def Percentage(total, curValue):
    return (float(curValue) * 100 / total)


def isEven(num):
    if num % 2 == 0:
        return True
    else:
        return False


def findInStr(findOut, findIn):
    result = False
    for word in findOut.split():
        if word.lower() in findIn.lower():
            result = True

    return result


def fixformat(name):
    for char in string.punctuation:
        if char != '-' and char != '_':
            name = name.replace(char, "_")
    return name.replace(" ", "_")


def cleanQueue(queue):
    while not queue.empty():
        item = queue.get()
        del item
    return

# replace urllib with urllib2


class FURLopener(urllib.FancyURLopener):

    def __init__(self, headers):
        urllib.FancyURLopener.__init__(self)
        self.setheaders(headers)
        socket.setdefaulttimeout(40)

    def __del__(self):
        socket.setdefaulttimeout(None)

    def setheaders(self, headers):
        self.addheaders = []
        for header in headers:
            self.addheaders.append((header, headers[header]))


class ImgDownload(threading.Thread):

    def __init__(self, name, suffix, link, maxRetrys, headers, tempDir, queue):
        super(ImgDownload, self).__init__()
        self.name = name
        self.suffix = suffix
        self.link = link
        self.headers = headers
        self.tempDir = tempDir
        self.queue = queue
        self.maxRetry = maxRetrys
        self.start()

    def run(self):
        while True:
            try:
                FURLopener(self.headers).retrieve(
                    'http://fufufuu.net%s' % self.link, os.path.join(
                        self.tempDir, "%s.%s" % (self.name, self.suffix)))
            except (OSError, IOError):
                if self.maxRetry == 0:
                    return
                self.maxRetry -= 1
            else:
                self.queue.task_done()
                return


class NotFound(Exception):

    def __init__(self, path):
        super(NotFound, self).__init__()
        self.errmsg = path

    def __str__(self):
        return self.errorMsg

if __name__ == '__main__':
    main()
