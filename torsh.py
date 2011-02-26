#! /bin/env python

from __future__ import unicode_literals, print_function

import cmd
import getopt
import socket
import sys
import getpass
import os
from termcolors import colorize
from subprocess import Popen, PIPE, call

from pytorctl import TorCtl, PathSupport, TorUtil

import formatter

class TorSH(cmd.Cmd):
  """ Shell for talking to Tor and debugging """
  def __init__(self, init_file = None):
    self.prompt = "%s # " % colorize("torsh", fg="red", opts=("bold",))
    self.completekey = "\t"
    self.cmdqueue = []
    self.stdout = sys.stdout
    TorUtil.logfile = "torsh.log"

    self._socket = None
    self._connection = None
    self._threads = None

    self._path = None
    self._selmgr = PathSupport.SelectionManager(
        pathlen=3,
        order_exits=True,
        percent_fast=80,
        percent_skip=0,
        min_bw=1024,
        use_all_exits=True,
        uniform=True,
        use_exit=None,
        use_guards=True)

    self._do_aliases()

    if init_file:
      try:
        self._execute_file(init_file)
      except Exception as e:
        print(e)


  def do_EOF(self, line):
    if self._connection:
      self._connection.close()
    
    return True

  def precmd(self, line):
    line = line.strip()

    if len(line) < 1:
      return ""

    if line[0:2] == "./" or line[0] == "/":
      return "%s %s" % ("exec", line)

    return line

  def do_connect(self, data):
    """ 
    Connects to a Tor instance by ControlSocket or ControlPort.

    Usage:
      connect --method=port --host=<host> --port=<port number> --pass=<passphrase>
      or
      connect --method=socket --path=<socket_path>
    """

    controlport = True
    host = "localhost"
    port = 9051
    passphrase = None
    path = None

    try:
      opts, args = getopt.getopt(data.split(" "), "m:", \
          ["method=", "host=", "port=", "pass=",\
           "path="])

      for opt, arg in opts:
        if opt == "--method":
          if arg == "port":
            controlport = True
          elif arg == "socket":
            controlport = False
          else:
            raise Exception("Unkown method for connection. \
                Use sock for ControlSocket and port for ControlPort")
        elif opt == "--host":
          host = arg
        elif opt == "--port":
          port = int(arg)
        elif opt == "--pass":
          passphrase = arg
        elif opt == "--path":
          path = arg

      if not controlport:
        raise Exception("ControlSocket connection isn't supported yet, \
            use ControlPort instead.")

      self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      self._socket.connect((host,port))
      self._connection = PathSupport.Connection(self._socket)
      self._connection.debug(file("control.log", "w", buffering=0))
      self._threads = self._connection.launch_thread()
      auth_type, auth_value = self._connection.get_auth_type(), ""
      
      if auth_type == TorCtl.AUTH_TYPE.PASSWORD:
        if passphrase: auth_value = passphrase
        else:
          try: auth_value = getpass.getpass()
          except KeyboardInterrupt: return None
      elif auth_type == TorCtl.AUTH_TYPE.COOKIE:
        auth_value = self._connection.get_auth_cookie_path()

      self._connection.authenticate(auth_value)

      self._path = PathSupport.PathBuilder(self._connection, self._selmgr)
      self._connection.set_event_handler(self._path)
      self._connection.set_events([TorCtl.EVENT_TYPE.STREAM,
        TorCtl.EVENT_TYPE.BW,
        TorCtl.EVENT_TYPE.NEWCONSENSUS,
        TorCtl.EVENT_TYPE.NEWDESC,
        TorCtl.EVENT_TYPE.CIRC,
        TorCtl.EVENT_TYPE.STREAM_BW], True)

      self.prompt = "%s@%s:%s # " % (colorize("torsh", fg="red", opts=("bold",)),\
          colorize(host, fg="blue"),\
          colorize(str(port), fg="blue"))

    except getopt.GetoptError:
      # TODO: implement a generic usage function
      # self.usage() 
      print("ERROR at the arguments")
      return
    except Exception as e:
      print("ERROR:", e[0])

  def _do_pipe(self, cmds, output):
    """
      Pipes the output to the stdin of the bash piped commands in cmds
    """

    p2 = Popen(["bash", "-c", "|".join(cmds)], stdin=PIPE, stdout=PIPE)
    stdin = "\n".join(output)
    return p2.communicate(input=stdin)[0]

  def do_get_info(self, name):
    """
    Issues a GET-INFO command with the first element of name.
    If name has more than one word, it's ignored.

    Usage:
      get-info network-status
      get-info addr-mappings/all
    """

    try:
      pipes = name.split("|")
      if len(pipes) > 1:
        names = pipes[0].split(" ")
        output = self._connection.get_info(names)
        output = self._do_pipe(pipes[1:], formatter.select_formatter(names[0], output[names[0]]))
      else:
        output = self._connection.get_info(name.split(" ")[:1])
        output = "\n".join(formatter.select_formatter(name, output[name]))
      print(output)
    except Exception as e:
      print("ERROR:", e)

  def do_set_options(self, keyvalues):
    """
      Issues a SETCONF command.

      Usage:
        set_options key1=val1 key2=val2 ...
    """

    keyvalue_list = keyvalues.split(" ")
    final_list = []
    for keyvalue in keyvalue_list:
      pair = keyvalue.split("=")
      final_list.append((pair[0], pair[1]))

    try:
      output = self._connection.set_options(final_list)
      print(formatter.format_reply(output[0]))
    except Exception as e:
      print(e[0])

  def do_reset_options(self, keys):
    """
      Issues a RESETCONF for the given keys.

      Usage:
        reset_conf key1 key2
    """

    try:
      output = self._connection.reset_options(keys.split(" "))
      print(formatter.format_reply(output[0]))
    except Exception as e:
      print(e[0])

  def do_get_option(self, name):
    """
      Issues a GETCONF.

      Usage:
        get_option key1 key2 ...
    """

    try:
      output = self._connection.get_option(name)
      formatted = formatter.format_getconf(output)
      for line in formatted:
        print(line)
    except Exception as e:
      print(e[0])

  def do_cat(self, line):
    """
      Just passes the whole command to bash to handle it.
    """
    p2 = Popen(["bash", "-c", line])

  def do_last_exit(self, line):
    """
      Returns the last exit used (metatroller based)
    """

    try:
      print(self._path.last_exit)
    except Exception as e:
      print(e[0])

  def do_shell(self, line):
    """
      Calls bash to interpret this command.
    """

    try:
      p2 = call(["bash", "-c", line])
    except Exception as e:
      print(e)

  def do_exec(self, file):
    """
      Executes the script in the file specified.
    """
    try:
      self._execute_file(file.strip())
    except Exception as e:
      print(e)

  def _do_aliases(self):
    """
      Builds short aliases for the common commands
    """

    self.do_conn = self.do_connect
    self.do_gi = self.do_get_info
    self.do_so = self.do_set_options
    self.do_go = self.do_get_option
    self.do_ro = self.do_reset_options

    self.do_le = self.do_last_exit

  def _execute(self, script):
    """
      Executes the linebreak separated script 
      one line at a time.
    """

    lines = script.split("\n")
    for line in lines:
      self.onecmd(self.precmd(line))

  def _execute_file(self, file):
    """
      It reads the whole file and executes it.
    """

    f = open(file, "r")
    script = f.read()
    self._execute(script)

def usage():
  print("Usage: ...")

if __name__ == '__main__':
  init_file = None
  try:
    opts, args = getopt.getopt(sys.argv[1:], "i:h", ["init=", "help"])
  except getopt.GetoptError, err:
    print(str(err))
    usage()
    sys.exit(2)

  for o, a in opts:
    if o in ("-h", "--help"):
      usage()
      sys.exit()
    elif o in ("-i", "--init"):
      init_file = a

  torsh = TorSH(init_file)
  torsh.cmdloop()
