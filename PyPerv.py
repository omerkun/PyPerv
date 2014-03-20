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
                    Chrome/6.0.472.14 Safari/534.3""", 'Accept-Encoding': 'gzip'}

# this class belongs to helper classes section
class Memo:
    """memorizer for mangaList because we don't want to use unnecessary
         bandwidth """

    def __init__(self, func):
        self.func = func
        self.list = None

    def __call__(self):
        if self.list is not None:
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
        html = getSource('http://www.fufufuu.net/tanks/', headers)
    except urllib2.URLError:
        print "No internet connection !"
        raise SystemExit

    tree = ET.ElementTree(ET.HTML(html))
    mangaElements = tree.findall('//li[@class="tli"]/a')
    mangalist = []
    for elem in mangaElements:
        mangalist.append((elem.getchildren()[0].text, elem.attrib.get('href')))
    return mangalist


def searchForManga(keyWord):
    resultList = []
    mainURL = 'http://fufufuu.net/search?'
    parKwd = urllib.urlencode({'q': keyWord})
    try:
        page = getSource(mainURL + parKwd, headers)
    except urllib2.URLError:
        print 'Connection Lost !!!'
        raise SystemExit

    tree = ET.ElementTree(ET.HTML(page))
    aElms = tree.findall('//li[@class="mli"]/a')
    pElms = tree.findall('//li[@class="mli"]/p')
    for elm in pElms:
        resultList.append(
            (elm.text, aElms[pElms.index(elm)].attrib.get('href')))

    selectMangaAndChapters(resultList)


def selectMangaAndChapters(sResult=None):
    target = None
    if not sResult:
        manga = parseInput()
        mangaList = getList()
    else:
        manga = 'all'
        mangaList = sResult

    if manga.lower() == 'all':
            for manga in mangaList:
                print "%i) %s" % (mangaList.index(manga) + 1, manga[0])
            while 1:
                ans = raw_input(
                    '\nplease enter the number of the manga you want: ')
                print "\n"
                try:
                    target = mangaList[int(ans.strip()) - 1]
                except IndexError:
                    print "Can't find manga at index %s" % ans
                except ValueError:
                    print "\nlet's try with the site search :)"
                    break
                else:
                    break
    else:
        miniList = []
        for mangaOnline in mangaList:
            if manga.lower() == mangaOnline[0].lower():
                target = mangaOnline
                break
            elif findInStr(manga, mangaOnline[0]):
                    miniList.append(mangaOnline)

    if not target:
        if miniList:
            for manga in miniList:
                print '%i) %s' % (miniList.index(manga) + 1, manga[0])
            print "\nI couldn't find your manga So !"
            print "those are some kind similar"

            while 1:
                ans = raw_input('Type the index of the manga you want: ')
                print "\n"
                try:
                    target = miniList[int(ans.strip()) - 1]
                except IndexError:
                    print "Can't find manga at index %s" % ans
                except ValueError:
                    print '\nLets try with the site search :)'
                    break
                else:
                    break
        else:
            print 'No similar manga !!!\nLets try with the site search :)'

    if target:
        link = target[1]
        try:
            page = getSource('http://fufufuu.net%s' % link, headers)
        except urllib.URLopener:
            print '\nConnection lost !!!'
            raise SystemExit
        tree = ET.ElementTree(ET.HTML(page))
        chapterElements = tree.findall('//li[@class="mli"]/a');chapterElements.reverse()
        chapterNames = tree.findall('//p[@class="mli-title"]');chapterNames.reverse()
        for chapterName in chapterNames :
            print "%i) %s" % (chapterNames.index(chapterName) + 1, chapterName.text)
        rawList = raw_input(
            '\nPlease type the number of chapter(s) you want separate with a space or ,: ')
        rawList = rawList.replace(" ", ",").split(",")
        for ch in rawList:
            try:
                link = chapterElements[int(ch) - 1].get('href')
                name = link.split('/')[-2]
                downloadChapter(target[0], name, link)
            except (ValueError, IndexError):
                print "can't find chapter at index %s" % ch
                raise SystemExit
    else:
        searchForManga(manga)

#! add threads for multi chapter download


def downloadChapter(mangaName, name, link):
    try:
        mainPage = getSource('http://www.fufufuu.net/%s' % link, headers)
    except urllib2.URLError:
        print "Connection lost !!!"
        raise SystemExit

    tree = ET.ElementTree(ET.HTML(mainPage))
    patPages = re.compile('\d{1,3}')
    pages = int(re.search(
        patPages, tree.find("//span[@class='text-small']").text).group())
    patLinks = re.compile('/media/p/\w{1,3}/\w{1,3}/\w+.\w{3}')
    imgLinks = re.findall(patLinks, tree.find('//div[@id="payload"]').text)
    tempDir = tempfile.mkdtemp()
    imgPool = Queue.Queue(2)
    try:
        for img in imgLinks:
            if isEven(imgLinks.index(img)):
                thread = ImgDownload(
                        str((imgLinks.index(img) / 2) + 1),
                             img.split('.')[-1], img, headers, tempDir, imgPool)
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
        except (urllib2.URLError, socket.timeout):
            if maxRetrys == 0:
                raise urllib2.URLError("Can't connect !!")
                break
            else:
                time.sleep(random.uniform(0.5 * timeWait, 1.5 * timeWait))
                maxRetrys -= 1

    socket.setdefaulttimeout(None)
    return source


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

    def setheaders(self, headers):
        self.addheaders = []
        for header in headers:
            self.addheaders.append((header, headers[header]))

    def http_error_706(self, url, fp, errmsg, headers, data=None):
        pass


class ImgDownload(threading.Thread):

    def __init__(self, name, suffix, link, headers, tempDir, queue):
        super(ImgDownload, self).__init__()
        self.name = name
        self.suffix = suffix
        self.link = link
        self.headers = headers
        self.tempDir = tempDir
        self.queue = queue
        self.start()

    def run(self):
        while True:
            try:
                FURLopener(self.headers).retrieve(
                    'http://fufufuu.net%s' % self.link, os.path.join(
                        self.tempDir, "%s.%s" % (self.name, self.suffix)))
            except OSError:
                pass
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
