### General utilities for convenience
### nothing real snazzy

## Geometry calculations
def box_contains_box(box1, box2):
  if box2 == None:
    return True
  elif box1 == None:
    return False
  else:
    return (box1[0] <= box2[0] <= box1[2]
        and box1[0] <= box2[2] <= box1[2]
        and box1[1] <= box2[1] <= box1[3]
        and box1[1] <= box2[3] <= box1[3])
def box_contains_point(box, point):
  if box == None:
    return False
  else:
    min_x, min_y, max_x, max_y = box
    x, y = point
    return min_x <= x < max_x and min_y <= y < max_y
def box_union(box1, box2):
  if box2 == None:
    return box1
  elif box1 == None:
    return box2
  else:
    return (min(box1[0], box2[0]), min(box1[1], box2[1]),
            max(box1[2], box2[2]), max(box1[3], box2[3]))
def box_intersection(box1, box2):
  if box1 == None or box2 == None:
    return None
  else:
    intersection = (
      max(box1[0], box2[0]), max(box1[1], box2[1]),
      min(box1[2], box2[2]), min(box1[3], box2[3])
    )
    if intersection[0] >= intersection[2] or intersection[1] >= intersection[3]:
      return None
    else:
      return intersection



def append_tag(widget, tag):
  cur_tags = widget.bindtags()
  widget.bindtags(cur_tags + (tag,))
def prepend_tag(widget, tag):
  cur_tags = widget.bindtags()
  widget.bindtags((tag,) + cur_tags)
def remove_tag(widget, tag):
  cur_tags = widget.bindtags()
  new_tags = [t for t in cur_tags if t != tag]
  widget.bindtags(tuple(new_tags))

## Event data communication
## Because Tkinter fails to implement the Event.data field, it is difficult
## to communicate information about virtual events important for optimizing
## certain functions. These functions make this communication possible by
## allowing widgets to register and retrieve information using a unique,
## randomly generated integer. This integer should be stored in the state field
## of the event.
event_data = dict()
def event_data_register(data, widget = None, expires = None):
  """ Registers the given data to a randomly generated integer key, which is returned.
  If you would like the data to be cleaned up after a certain amount of time, the
  widget and expires arguments allow you to use widget.after() to schedule the data
  to be deleted after expires milliseconds. """
  import random
  key = random.randint(0,10**6)
  event_data[key] = data

  ## Optionally delete the event data after a certain amount of time
  ## This is useful if you're generating a lot of events and need to save memory.
  ## Note that most events will get handled very quickly, so expiration after
  ## even a second is probably overkill unless you need to store the data
  ## long term (in which case you should probably store it somewhere else...) :)
  if expires != None and widget != None:
    widget.after(expires, event_data_remove, key)

  return key
def event_data_retrieve(key):
  if key in event_data:
    return event_data[key]
  else:
    return None
def event_data_remove(key):
  del event_data[key]

def color_str_to_tuple(color_str):
  depth = (len(color_str) - 1)/3
  color_data = []
  for i in range(1, len(color_str), depth):
    color_data.append(int(color_str[i:i+depth], base=16) / float(16**depth - 1))
  return tuple(color_data)
def color_tuple_to_str(color_tuple):
  return '#' + ''.join(['%03x'%(int(v * 4095)) for v in color_tuple])
def color_blend(color1, color2, weight):
  color1_tup = color_str_to_tuple(color1)
  color2_tup = color_str_to_tuple(color2)
  blended = []
  for v1, v2 in zip(color1_tup, color2_tup):
    blended.append(v1 * weight + v2 * (1 - weight))
  return color_tuple_to_str(blended)
