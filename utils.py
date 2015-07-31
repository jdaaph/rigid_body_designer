### General utilities for convenience
### nothing real snazzy

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
def event_data_register(data):
  import random
  key = random.randint(0,10**6)
  event_data[key] = data
  return key
def event_data_retrieve(key):
  return event_data[key]