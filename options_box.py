import Tkinter as tk
import ttk
import tkFileDialog

import itertools as it
import re

from model import Model
from model_canvas import ModelCanvas
from brush import Brush
#from Operation import Group_Set

import utils

def tuple2color(vals):
  str_vals = map(lambda n: format(n%4096, '03x'), vals)
  return '#' + ''.join(str_vals)


sticky_all = tk.N + tk.S + tk.E + tk.W

class OptionsBox(tk.Frame):
  models_box = None
  tool_box = None
  edit_box = None
  io_box = None
  operation_box = None

  #brush_change_callbacks = None
  model_change_callbacks = None

  prev_brush = None

  def __init__(self, master, model_func=None, export_func=None, import_func=None):
    tk.Frame.__init__(self, master)

    # self.brush_change_callbacks = []
    self.model_change_callbacks = []

    self.rowconfigure(0, weight = 1)
    self.columnconfigure(0, weight = 1)

    self.models_box = ModelsBox(master = self,
        model_func = model_func, callback = self.trigger_model_change)
    self.tool_box = ToolBox(master = self, callback = self.trigger_brush_change)
    # self.add_brush_change_callback(self.tool_box.update_buttons)
    self.edit_box = BrushEditorBox(master = self)
    # self.add_brush_change_callback(self.edit_box.update_fields)

    # add this callback to make use of Operations.Group_Set and trans_model_copy
    #self.add_brush_change_callback(self.watchdog_group_set)
    #self.add_model_change_callback(self.watchdog_trans_model_op)

    self.io_box = IOBox(master = self, export_func = export_func, import_func = import_func)
    self.operation_box = OperationBox(master=self)

    self.models_box.grid(sticky = sticky_all)
    self.tool_box.grid(sticky = sticky_all)
    self.edit_box.grid(sticky = sticky_all)
    self.io_box.grid(sticky = sticky_all)
    self.operation_box.grid(sticky = sticky_all)
    
    self.prev_brush = self.get_brush()
    self.trigger_brush_change()

#  def get_default_brush(self):
#    return self.tool_box.default_brush
  def get_brush(self):
    return self.tool_box.get_brush()
  def get_model(self):
    return self.models_box.get_model()
  def get_models(self):
    return self.models_box.get_models()
  def get_copies(self):
    return self.models_box.get_copies()

#  def add_brush_change_callback(self, func):
#    self.brush_change_callbacks.append(func)
  def trigger_brush_change(self):
    key = utils.event_data_register(self.get_brush())
    self.event_generate('<<Brush>>', state = key)
    print 'Generated <<Brush>> event:', self.get_brush()

  def add_model_change_callback(self, func):
    self.model_change_callbacks.append(func)
  def trigger_model_change(self):
    self.event_generate('<<ModelSelect>>', state = utils.event_data_register(self.get_model()))
    print 'Generated <<ModelSelect>> event:', self.get_model()
    for f in self.model_change_callbacks:  f()

  def set_particle_specs(self, specs):
    self.tool_box.set_particle_specs(specs)
  def set_body_specs(self, specs):
    self.tool_box.set_body_specs(specs)
  def set_models(self, models):
    self.models_box.set_models(models)

  # def watchdog_group_set(self):
  #   '''This is added to the brush_change_callback, the watchdog that will enable group_set to detect brush change'''
  #   # This ugly try is to surpass the first brush_change_callback when initializing the app
  #   
  #   try:
  #     model = self.models_box.get_model()
  #     if model.selected_particles:
  #       model.current_operation = Group_Set(model=model, cache={'selected':model.selected_particles, 'not_selected':model.not_selected(), 'old_brush':self.prev_brush},
  #         operation_box=self.operation_box) 
  #     curr_op = model.current_operation
  #     brush = model.get_brush()
  #     brush_not_empty = (brush.particle_specs) and (brush.body_specs)
  #     # fill the cache with new brush specs, and if new brush spec has an empty entry, wait for the next valid input
  #     if isinstance (curr_op, Group_Set) and brush_not_empty:
  #       curr_op.fill_cache(brush)
  #       curr_op.paste()
  #     elif isinstance (curr_op, Group_Set) and not brush_not_empty:
  #       pass
  #     self.prev_brush = self.get_brush()
  #   except IndexError:
  #     pass

  # def watchdog_trans_model_op(self):
  #   ''' Used to monitor model change, will pass the current model's current_op to the next selected model '''
  #   # This ugly try is to surpass the first model_change_callback when initializing the app
  #   # note this is called by the ModelList class
  #   prev_model = self.models_box.canvas.prev_model
  #   new_model = self.models_box.get_model()
  #   if prev_model and prev_model.current_operation and (prev_model is not new_model):
  #     new_model.current_operation, prev_model.current_operation  = prev_model.current_operation, None
  #     new_model.current_operation.model = new_model
  #     new_model.current_operation.cache['not_selected'] = new_model.particles
  #   self.models_box.canvas.prev_model = new_model


class ModelsBox(tk.Frame):
  canvas = None
  add_button = None
  def __init__(self, master, model_func, callback):
    tk.Frame.__init__(self, master)

    self.rowconfigure(0, weight = 1)
    self.columnconfigure(0, weight = 1)

    self.canvas = self.ModelsList(self, model_func, callback)
    self.canvas.grid(row = 0, column = 0, sticky = sticky_all)

    self.add_button = tk.Button(self, text = '+', command = self.canvas.add_model)
    self.add_button.grid(row = 1, column = 0, columnspan = 2, sticky = sticky_all)

    yscrollbar = tk.Scrollbar(self, orient = tk.VERTICAL, command = self.canvas.yview)
    self.canvas['yscrollcommand'] = yscrollbar.set
    yscrollbar.grid(row = 0, column = 1, sticky = sticky_all)

  def get_model(self):
    return self.canvas.get_model()
  def get_models(self):
    return [elem.model for elem in self.canvas.models]
  def get_copies(self):
    return [elem.copies_var.get() for elem in self.canvas.models]

  def set_models(self, models):
    self.canvas.set_models(models)

  class ModelsList(tk.Canvas):
    frame = None
    models = None

    cur_idx = 0

    callback = None
    make_new_model = None

    # used for trans-model-copy option
    prev_model = None

    def __init__(self, master, model_func, callback):
      tk.Canvas.__init__(self, master, highlightthickness = 0)

      self.callback = callback
      self.make_new_model = model_func

      self.frame = tk.Frame(self)
      self.models = []

      self.create_window(0,0, window = self.frame, tags = 'frame', anchor = tk.N + tk.W)      
      self.frame.columnconfigure(0, weight = 1)

      self.bind('<Configure>', self.resize_frame)
      
      #self.add_model()

    def resize_frame(self, event):
      self.itemconfigure('frame', width = event.width)

    def add_model(self):
      model = self.make_new_model()
      elem = self.ListElement(self.frame, model)
      elem.grid(sticky = sticky_all)

      idx = len(self.models)
      self.models.append(elem)

      cell_height = self.models[0].winfo_height()
      self['scrollregion'] = (0, 0, 0, cell_height*(idx+1))

      elem.bind('<Button-1>', lambda e, i=idx: self.handle_click(e, i))

    def get_model(self):
      return self.models[self.cur_idx].model

    def set_models(self, models):
      for m in self.models:
        m.grid_forget()
      self.models = []
      for m in models:
        self.add_model()
        self.models[-1].model = m
      self.cur_idx = 0
      self.handle_click(object(), 0)

    def handle_click(self, event, idx):
      self.models[self.cur_idx]['bg'] = '#CCCCCC'
      self.models[self.cur_idx].update_thumbnail()

      self.cur_idx = idx
      self.models[idx]['bg'] = '#999'

      self.callback()

    class ListElement(tk.Frame):
      model = None
      copies_var = None

      thumbnail = None
      copies_entry = None

      def __init__(self, master, model = None):
        tk.Frame.__init__(self, master)
        self['bg'] = '#CCCCCC'

        self.model = model
        self.copies_var = tk.IntVar(self)

        self.columnconfigure(1, weight = 1)

        self.thumbnail = ModelCanvas(self, mode = 'view')
        self.thumbnail.configure(width = 100, height = 100)
        self.thumbnail.set_model(model)
        self.thumbnail.padding = 5
        self.thumbnail.grid(row = 0, column = 0, sticky = sticky_all)

        self.copies_entry = tk.Entry(self, textvariable = self.copies_var)
        self.copies_entry.grid(row = 0, column = 1, sticky = tk.E + tk.W)

        self.bind_all('<<Model>>', lambda e: self.update_thumbnail(), add='+')

      def update_thumbnail(self):
        pass


class ToolBox(tk.Frame):
  particle_buttons = None
  body_buttons = None

  particles = None
  bodies = None

  default_brush = None
  def __init__(self, master, callback):
    tk.Frame.__init__(self, master)

    self.columnconfigure(1, weight = 1)

    self.add_label("Particles:")
    self.add_label("Bodies:")

    particle_colors = it.chain(['#F00', '#0F0', '#00F', '#FF0', '#0FF', '#F0F'], it.imap(lambda n: tuple2color((n,n/5,n/7)), it.count(2000,3001)))
    body_colors = it.chain(['#A00', '#0A0', '#00A', '#AA0', '#0AA', '#A0A'], it.imap(lambda n: tuple2color((n/2,n/3,n/5)), it.count(2000,3001)))

    self.particles = it.imap(lambda c: Brush.ParticleSpecs(name = str(c[0]), color = c[1]), enumerate(particle_colors))
    self.bodies = it.imap(lambda c: Brush.BodySpecs(idx = c[0], color = c[1]), enumerate(body_colors))

    self.particle_buttons = ButtonList(self, text = unichr(0x25CF),
        object_iter = self.particles, callback = callback,
        num_init_buttons = 2) #0x25CF is filled circle
    self.particle_buttons.grid(column = 1, row = 0, sticky = tk.W + tk.E)
    self.body_buttons = ButtonList(self, text = unichr(0x25CB),
        object_iter = self.bodies, callback = callback) #0x25CB is empty circle
    self.body_buttons.grid(column = 1, row = 1, sticky = tk.W + tk.E)

    self.default_brush = Brush(self.particle_buttons.get_cur_object(), self.body_buttons.get_cur_object())


  def add_label(self, text):
    l = tk.Label(self, text = text, bg = self['bg'])
    l.grid(column = 0, sticky = tk.E)

  def update_buttons(self):
    self.particle_buttons.update_buttons()
    self.body_buttons.update_buttons()

  def get_brush(self):
    particle_specs = self.particle_buttons.get_cur_object()
    body_specs = self.body_buttons.get_cur_object()
    return Brush(particle_specs, body_specs)

  def set_particle_specs(self, specs):
    self.particle_buttons.set_objects(specs)
  def set_body_specs(self, specs):
    self.body_buttons.set_objects(specs)

class BrushEditorBox(tk.Frame):
  part_name_var = None
  part_color_var = None
  body_color_var = None

  part_name_entry = None
  part_color_entry = None
  body_color_entry = None

  get_brush = None
  # brush_change_callback = None
  def __init__(self, master):
    tk.Frame.__init__(self, master)
    
    self.part_name_var = tk.StringVar(self)
    self.part_color_var = tk.StringVar(self)
    self.body_color_var = tk.StringVar(self)

    self.columnconfigure(1, weight = 1)

    self.part_name_entry = self.add_field_editor('Particle Name:', self.part_name_var, 0)
    self.part_color_entry = self.add_field_editor('Particle Color:', self.part_color_var, 1)
    self.body_color_entry = self.add_field_editor('Body Color:', self.body_color_var, 2)

    self.bind_all('<<Brush>>', self.handle_brush_event, add='+')
    self.part_name_entry.bind('<Any-KeyRelease>', lambda e: self.update_particlespecs(), add='+')
    self.part_color_entry.bind('<Any-KeyRelease>', lambda e: self.update_particlespecs(), add='+')
    self.body_color_entry.bind('<Any-KeyRelease>', lambda e: self.update_bodyspecs(), add='+')

    # self.get_brush = self.winfo_toplevel().get_brush
    # self.brush_change_callback = callback

  def add_field_editor(self, field_name, field_var, row):
    label = tk.Label(self, text = field_name, bg = self['bg'])
    entry = tk.Entry(self, textvariable = field_var)

    label.grid(row = row, column = 0, sticky = tk.E)
    entry.grid(row = row, column = 1, sticky = sticky_all)
    return entry

  def handle_brush_event(self, event):
    # brush = self.get_brush()
    brush = utils.event_data_retrieve(event.state)

    if brush.particle_specs == None:
      self.part_name_entry['state'] = tk.DISABLED
      self.part_color_entry['state'] = tk.DISABLED
    else:
      self.part_name_entry['state'] = tk.NORMAL
      self.part_color_entry['state'] = tk.NORMAL
      self.part_name_var.set(brush.particle_specs.name)
      self.part_color_var.set(brush.particle_specs.color)
      print brush.particle_specs.color

    if brush.body_specs == None:
      self.body_color_entry['state'] = tk.DISABLED
    else:
      self.body_color_entry['state'] = tk.NORMAL
      self.body_color_var.set(brush.body_specs.color)

  def validate_color(self, color):
    return re.match(r"^#([0-9A-Fa-f]{3}){1,3}$", color)
  def update_particlespecs(self):
    if not self.validate_color(self.part_color_var.get()):
      return
    name = self.part_name_var.get()
    color = self.part_color_var.get()
    key = utils.event_data_register(dict(name = name, color = color))
    self.event_generate('<<ParticleSpecs>>', state = key)
  def update_bodyspecs(self):
    if not self.validate_color(self.body_color_var.get()):
      return
    color = self.body_color_var.get()
    key = utils.event_data_register(dict(color = color))
    self.event_generate('<<BodySpecs>>', state = key)


    
class ButtonList(tk.Frame):
  """ Contains a list of radio buttons, each corresponding to a series of arbitrary objects.
  Radio buttons are added by pressing the '+' button. Each object must have a color attribute
  for convenience. """

  button_holder = None  # Holds the radio buttons
  button_adder = None # Use to add additional buttons

  object_iter = None # Iterator to produce objects associated with radiobuttons. Number of buttons allowed is limited only by iterator length

  buttons = None # List of buttons in the button_holder
  objects = None # List of objects associated with the above buttons

  text = "" # Text to be placed in each radio button

  cur_idx = None # stores internally the correct index to be selected
  button_var = None # tk.IntVar used to manipulate which buttons are activated

  callback = None # stores all functions to call whenever the selected button changes

  def __init__(self, master, text, object_iter, callback, num_init_buttons = 1):
    tk.Frame.__init__(self, master, bg = master['bg'])

    self.buttons = []
    self.objects = []

    self.object_iter = iter(object_iter)

    self.text = text

    self.cur_idx = 0
    self.button_var = tk.IntVar(self, self.cur_idx)

    self.callback = callback

    ## Create widgets
    self.button_holder = tk.Text(self, height = 1, width = 10, state = tk.DISABLED, background = self['bg'], highlightthickness = 0)

    ttk.Style().configure('ButtonList.TButton', background = self['bg'], width = -1)
    self.button_adder = ttk.Button(self, text = "+", command = self.add_button, style = 'ButtonList.TButton')

    ## Layout widgets
    self.columnconfigure(0, weight = 1)
    self.button_holder.grid(row = 0, column = 0, sticky = sticky_all)
    self.button_adder.grid(row = 0, column = 1)

    ## Add initial number of buttons
    for i in range(num_init_buttons):
      self.add_button()

  def add_button(self):
    idx = len(self.buttons) # Index of new button
    obj = self.object_iter.next()
    color = obj.color  # next color to use
    style_name = '{0}.TRadiobutton'.format(color)
    ttk.Style().configure(style_name, foreground = color, background = self['bg'])
    b = ttk.Radiobutton(self, style = style_name, text = self.text,
                       value = idx, variable = self.button_var, command = lambda: self.toggle_select(idx))
    self.button_holder.window_create(tk.END, window = b)

    self.buttons.append(b)
    self.objects.append(obj)

  def get_cur_idx(self):
    return self.cur_idx
  def set_cur_idx(self, v):
    self.cur_idx = v
    self.button_var.set(v)
  def get_cur_object(self):
    if self.get_cur_idx() != -1:
      return self.objects[self.get_cur_idx()]
    else:
      return None

  def update_buttons(self):
    for button, obj in zip(self.buttons, self.objects):
      style_name = '{0}.TRadiobutton'.format(obj.color)
      ttk.Style().configure(style_name, foreground = obj.color)

  def toggle_select(self, idx):
    if self.get_cur_idx() != idx:
      self.set_cur_idx(idx)
    else:
      self.set_cur_idx(-1)
    self.callback()

  def set_objects(self, objs):
    while len(self.objects) < len(objs):
      self.button_adder.invoke()

    for cur_obj, new_obj in zip(self.objects, objs):
      cur_obj.copy_attributes(new_obj)

    self.update_buttons()
    self.callback()


class IOBox(tk.Frame):
  file_label = None
  choose_file_button = None
  export_button = None
  import_button = None

  file_path_var = None

  def __init__(self, master, export_func, import_func):
    tk.Frame.__init__(self, master)

    self.file_path_var = tk.StringVar(self)

    self.initWidgets(export_func, import_func)
    self.layoutWidgets()

  def initWidgets(self, export_func, import_func):
    ## Initialize all widgets of the ExportBox

    ## Make file label (shows path to file destination)
    self.file_label = tk.Label(master = self, textvariable = self.file_path_var)

    ## Make file button (for choosing file destination)
    self.choose_file_button = tk.Button(master = self, text = "...", command = self.set_export_destination)

    ## Make export button (for triggering export of data)
    self.export_button = tk.Button(master = self, text = "Export", command = lambda: export_func(self.file_path_var.get()))

    self.import_button = tk.Button(master = self, text = "Import", command = import_func)
  def layoutWidgets(self):
    ## Configure columns so that first column (with the file-path label)
    ## gets expanded
    self.columnconfigure(0, weight = 1)

    ## Add components
    self.file_label.grid(row = 0, column = 0, sticky = tk.E + tk.N + tk.S)
    self.choose_file_button.grid(row = 0, column = 1, sticky = sticky_all)
    self.export_button.grid(row = 1, columnspan = 2, sticky = sticky_all)
    self.import_button.grid(row = 2, columnspan = 2, sticky = sticky_all)

  def set_export_destination(self):
    path = tkFileDialog.asksaveasfilename(title = "Choose export path...", defaultextension=".xml", filetypes=[("XML", "*.xml"), ("RBD", "*.rbd")])
    self.file_path_var.set(path)


class OperationBox(tk.Frame):
  hint_label = None
  cache_label = None
  cancel_button = None

  # var holds the strings to be displayed on GUI
  var_hint = None
  var_cache = None
  current_operation = None

  def __init__(self, master):
    tk.Frame.__init__(self, master)

    self.var_hint = tk.StringVar(self)
    self.var_cache = tk.StringVar(self)
    self.current_operation = None

    self.initWidgets()
    self.layoutWidgets()

  def initWidgets(self):
    self.hint_label = tk.Label(master = self, textvariable = self.var_hint)
    self.cache_label = tk.Label(master = self, textvariable = self.var_cache)
    ## Make cancel_button, for cancel current operation and dump the cache
    self.cancel_button = tk.Button(master = self, text = "Cancel Operation", command = lambda: self.current_operation.cancel() if self.current_operation else None)

  def layoutWidgets(self):
    ## Configure columns so that first column (with the file-path label)
    ## gets expanded
    self.columnconfigure(0, weight = 1)

    ## Add components
    self.hint_label.grid(row = 0, column = 0, sticky = tk.E + tk.N + tk.S)
    self.cache_label.grid(row = 1, column = 0, sticky = tk.E + tk.N + tk.S)
    self.cancel_button.grid(row = 2, columnspan = 2, sticky = sticky_all)


