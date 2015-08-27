import Tkinter as tk
import ttk

import utils
from tools import ModelSelectBox, BrushSelectBox, BrushEditBox, IOBox, OperationBox


sticky_all = tk.N + tk.S + tk.E + tk.W



def tuple2color(vals):
  str_vals = map(lambda n: format(n%4096, '03x'), vals)
  return '#' + ''.join(str_vals)


class ToolBox(tk.Frame):

  prev_brush = None

  def __init__(self, master, export_func=None, import_func=None):
    tk.Frame.__init__(self, master)

    self.rowconfigure(0, weight = 1)
    self.columnconfigure(0, weight = 1)

    self.models_box = ModelSelectBox(master = self, callback = self.model_select_callback)
    self.brush_box = BrushSelectBox(master = self, callback = self.brush_select_callback)
    self.edit_box = BrushEditBox(master = self,
      particlespecs_callback = self.particle_specs_change_callback,
      bodyspecs_callback = self.body_specs_change_callback)
    self.io_box = IOBox(master = self, export_func = export_func, import_func = import_func)
    #self.operation_box = OperationBox(master=self)

    self.models_box.grid(sticky = sticky_all)
    self.brush_box.grid(sticky = sticky_all)
    self.edit_box.grid(sticky = sticky_all)
    self.io_box.grid(sticky = sticky_all)
    #self.operation_box.grid(sticky = sticky_all)
    
    self.brush_select_callback(self.get_brush())


  def get_model(self):
    return self.models_box.get_selected_model()
  def get_models(self):
    return self.models_box.get_models()
  def set_models(self, models):
    self.models_box.set_models(models)
  def get_copies(self):
    return self.models_box.get_copies()

  def get_brush(self):
    return self.brush_box.get_brush()

  def set_particle_specs(self, specs):
    self.brush_box.set_particle_specs(specs)
  def set_body_specs(self, specs):
    self.brush_box.set_body_specs(specs)


  def model_select_callback(self, data = None):
    self.event_generate('<<ModelSelect>>', state = utils.event_data_register(data))
    print 'Generated <<ModelSelect>> event:', data

  def brush_select_callback(self, data = None):
    key = utils.event_data_register(data)
    self.event_generate('<<Brush>>', state = key)
    print 'Generated <<Brush>> event:', data

  def particle_specs_change_callback(self, data = None):
    self.event_generate('<<ParticleSpecs>>', state = utils.event_data_register(data))
    print 'Generated <<ParticleSpecs>> event:', data

  def body_specs_change_callback(self, data = None):
    self.event_generate('<<BodySpecs>>', state = utils.event_data_register(data))
    print 'Generated <<BodySpecs>> event:', data
    