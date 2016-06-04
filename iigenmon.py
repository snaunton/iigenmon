#!/usr/bin/env python3
#
#    Copyright (C) 2016 Simon Naunton
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

from lxml import etree
from urllib.request import urlopen
from sys import exit
from os.path import expanduser
from os.path import exists
from os import makedirs
import datetime
import configparser
import keyring
import getopt
import sys

class iigenmon:
  usagestr = "Usage: iigenmon.py [-p <password>] username\n\nWhen -p <password> is used, password for username is saved and then program exits"
  error = None
  display_usage = False;
  days_remaining = None;
  anytime = None
  uploads = None
  quota_allocation = None
  percent_used = 0
  retrieved = None
  cfg = None
  cfgfn = None

  def __init__(self, argv):
    username = None
    password = None

    try:
      opts, args = getopt.getopt(argv,"p:")
      for opt, arg in opts:
        if opt == "-p":
          password = arg
      if args:
        username = args[0]

    except getopt.GetoptError as ex_error:
      if ex_error.opt == "p":
        print("ERROR: no password");
        print(self.usagestr)
        return
      else:
        self.usage(str(ex_error))

    # -p <password> on command line
    # save <password> to keyring and exit
    if password:
      if not username:
        print("ERROR: No username");
        print(self.usagestr)
      else:
        keyring.set_password("iigenmon.py", username, password)
      return

    if not username:
      self.usage("No username")

    password = keyring.get_password("iigenmon.py", username)
    if not password:
      self.usage("No password")

    self.initCache(username)
    tree = self.getXML(username,password)

    if tree != None:
      self.useXML(tree) 
    else:
      self.useCache()

    self.display()

  def usage(self,message):
    self.display_usage = True;
    self.error = message
    self.display()
    exit(2)

  def initCache(self,username):
    self.cfg = configparser.ConfigParser(allow_no_value=True)
    cache_dir = '%s/.cache/iigenmon.py' % expanduser("~")
    self.cfgfn = '%s/%s' % (cache_dir,username)
    if not exists(cache_dir):
      makedirs(cache_dir)

  def getXML(self,u,p):
    try:
      xml = urlopen('https://toolbox.iinet.net.au/cgi-bin/new/volume_usage_xml.cgi?username=%s&action=login&password=%s' % (u,p)).read()
      tree = etree.fromstring(xml)
      error_xml = tree.xpath('//ii_feed/error/text()')

      if len(error_xml) > 0:
        self.error = "Error in XML: %s" % error_xml[0]
      else:
        return tree;

    except Exception as ex_error:
      self.error = "Exception getting XML: %s" % str(ex_error)

    return None

  def useXML(self,tree):
    self.days_remaining = tree.xpath('//ii_feed/volume_usage/quota_reset/days_remaining/text()')[0]
    self.anytime = tree.xpath('//ii_feed/volume_usage/expected_traffic_types/type[@classification="anytime"]/@used')[0]
    self.uploads = tree.xpath('//ii_feed/volume_usage/expected_traffic_types/type[@classification="uploads"]/@used')[0]
    self.quota_allocation = tree.xpath('//ii_feed/volume_usage/expected_traffic_types/type[@classification="anytime"]/quota_allocation/text()')[0]
    self.percent_used = (100.0/(int(self.quota_allocation) * 1024 * 1024)) * (int(self.anytime) + int(self.uploads))
    self.retrieved = datetime.datetime.now().strftime("%c")

    self.cfg['LAST'] = {'days_remaining': self.days_remaining,
                    'anytime': self.anytime,
                    'uploads': self.uploads,
                    'quota_allocation': self.quota_allocation,
                    'percent_used': self.percent_used,
                    'retrieved': self.retrieved}

    with open(self.cfgfn, 'w') as cf:
      self.cfg.write(cf)
      cf.close()

  def useCache(self):
    try:
      self.cfg.read(self.cfgfn)
      self.days_remaining = self.cfg['LAST']['days_remaining']
      self.anytime = self.cfg['LAST']['anytime']
      self.uploads = self.cfg['LAST']['uploads']
      self.quota_allocation = self.cfg['LAST']['quota_allocation']
      self.percent_used = self.cfg['LAST']['percent_used']
      self.retrieved = self.cfg['LAST']['retrieved']
    except Exception as ex_error:
      if not self.error:
        self.error = "%s not found\n%s" % (self.cfgfn, str(ex_error))      

  def display(self):
    print("<bar>%s</bar>" % self.percent_used)
    print("<tool>")
    if self.days_remaining:
      print("Days Remaining:", self.days_remaining)
    if self.anytime:
      print("Anytime: %.2fGb" % round(int(self.anytime)/1024/1024/1024+0.005,2))
    if self.uploads:
      print("Uploads: %.2fGb" % round(int(self.uploads)/1024/1024/1024+0.005,2))
    if self.quota_allocation:
      print("Quota: %sGb" % self.quota_allocation[0:-3])
    if self.percent_used:
      print("Percent Used: %.2f%%" % round(float(self.percent_used)+0.005,2))
    if self.retrieved:
      print("Retrieved: ", self.retrieved)
    if self.error:
      print("\nError: %s" % ' '.join(self.error.split(None)))
    if self.display_usage:
      print(self.usagestr)
    print("</tool>")

def main(args):
  iigenmon(args)

if __name__ == "__main__":
  main(sys.argv[1:])
