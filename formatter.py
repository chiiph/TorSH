def default_formatter(output):
  return output.split("\n")

def format_ns_all(output):
  return output.split("\n")

def select_formatter(name, output):
  if name == "ns/all":
    return format_ns_all(output)
  else:
    return default_formatter(output)
