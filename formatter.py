def default_formatter(output):
  return output.split("\n")

def format_ns_all(output):
  return output.split("\n")

def format_reply(output):
  if len(output) > 2:
    return "%s - %s" % (output[0], output[1])
  else:
    return " ".join(output)

def format_getconf(output):
  final = []
  for keyval in output:
    final.append("%s=%s" % (keyval[0], keyval[1]))
  
  return final

def format_exit_policy(output):
  return output.split(",")

def select_formatter(name, output):
  if name == "ns/all":
    return format_ns_all(output)
  elif name == "exit-policy/default":
    return format_exit_policy(output)
  else:
    return default_formatter(output)
