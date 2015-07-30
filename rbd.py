import Tkinter as tk
import ttk
import tkFileDialog

from design_box import DesignBox
from options_box import OptionsBox, OperationBox
# from Operation import Operation
from model import Model
import rbd_io

sticky_all = tk.N + tk.S + tk.W + tk.E

### TODO
# Implement virtual events for:
#  <<Brush>>          changes to currently selected brush
#  <<ParticleType>>   changes to characteristics of a particular particle type (i.e. name, color)
#  <<BodyType>>       changes to characteristics of a particular body type (i.e. color)
#  <<Model>>          changes to a Model object (adding/removing/painting particles)
#  <<ModelSelect>>    new model selected for editing
# Bind a widget to these events just as you would an ordinary event:
#  widget.bind('<<Brush>>', handler_function)
#
# Make Application query-able for global model-editing properties
#   get_brush()
#   get_current_model()
#   get_models()

class Application(tk.Frame):
  design_box = None
  options_box = None
  status_box = None

  def __init__(self, master = None):
    tk.Frame.__init__(self, master)

    self.initWidgets()

    self.layoutWidgets()

    self.event_generate('<<Brush>>')

  def initWidgets(self):
    self.design_box = DesignBox(self, brush_func = self.get_brush)
    self.options_box = OptionsBox(self, self.make_new_model, self.export_data, self.import_data)
    self.quitButton = tk.Button(self, text='Quit', command=self.quit)

    self.options_box.add_model_change_callback(self.update_design_box)

    self.options_box.models_box.canvas.add_model()
    self.options_box.models_box.canvas.handle_click(object(), 0)

  def layoutWidgets(self):
    ## Make overall layout resize with the top-level window
    top = self.winfo_toplevel()
    top.rowconfigure(0, weight = 1)
    top.columnconfigure(0, weight = 1)

    ## Set up internal layout grid for application
    self.grid(sticky = sticky_all)
    self.columnconfigure(0, weight = 3)
    self.columnconfigure(1, weight = 1)
    self.rowconfigure(0, weight = 1)

    ## Add widgets to grid
    self.design_box.grid(column = 0, row = 0, sticky = sticky_all)
    self.options_box.grid(column = 1, row = 0, sticky = sticky_all)
    self.quitButton.grid(column = 0, row = 1, columnspan = 1, sticky = sticky_all)

  def get_brush(self):
    if self.options_box == None:
      return None
    else:
      return self.options_box.get_brush()

  def get_current_model(self):
    pass

  def get_models(self):
    pass

  def make_new_model(self):
    model = Model()
    ##self.options_box.add_brush_change_callback(model.redraw_brush_change)
    return model
  def update_design_box(self):
    model = self.options_box.get_model()
    self.design_box.switch_model(model)

  def export_data(self, path):
    models = self.options_box.get_models()
    copies = self.options_box.get_copies()

    if path.endswith(".xml"):
      rbd_io.export_xml(path, models, copies)
      print "XML output written to", path
    elif path.endswith(".rbd"):
      particle_specs = self.options_box.tool_box.particle_buttons.objects
      body_specs = self.options_box.tool_box.body_buttons.objects
      rbd_io.export_rbd(path, models, particle_specs, body_specs)
      print ".rbd output written to", path
    else:
      print "Bad output path:", path

  def import_data(self):
    path = tkFileDialog.askopenfilename(title = "Choose import path...", defaultextension=".rbd", filetypes=[("RBD", "*.rbd"), ("All files", "*")])
    rbd_io.import_rbd(path, self)

  def cancel_operation(self):
    self.design_box.canvas.current_operation.cancel()
    



app = Application()


app.master.title('Rigid Body Designer')

app.mainloop()
app.quit()
