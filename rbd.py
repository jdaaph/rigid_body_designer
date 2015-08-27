import Tkinter as tk
import ttk
import tkFileDialog

from design_box import DesignBox
from tool_box import ToolBox
# from Operation import Operation
from model import Model
import rbd_io
import utils

sticky_all = tk.N + tk.S + tk.W + tk.E

### TODO
# Implement virtual events for:
#  <<Brush>>           changes to currently selected brush
#  <<ParticleSpecs>>   changes to characteristics of a particular particle type (i.e. name, color)
#  <<BodySpecs>>       changes to characteristics of a particular body type (i.e. color)
#  <<Model>>           changes to a Model object (adding/removing/painting particles)
#  <<ModelSelect>>     new model selected for editing
# Bind a widget to these events just as you would an ordinary event:
#  widget.bind('<<Brush>>', handler_function)
#
# Make Application query-able for global model-editing properties
#   get_brush()
#   get_current_model()
#   get_models()

class Application(tk.Frame):
  design_box = None
  tool_box = None
  status_box = None

  def __init__(self, master = None):
    tk.Frame.__init__(self, master)

    self.initWidgets()

    self.layoutWidgets()

    self.event_generate('<<Brush>>', state=utils.event_data_register(self.get_brush()))

    # Set focusing properties so the DesignCanvas is usually in focus
    self.bind_all('<ButtonPress-1>', self.handle_focus, add='+')

  def initWidgets(self):
    self.design_box = DesignBox(self)
    self.tool_box = ToolBox(self, self.export_data, self.import_data)
    self.quitButton = tk.Button(self, text='Quit', command=self.quit)

    self.tool_box.models_box.add_model()
    self.design_box.switch_model(self.tool_box.models_box.get_cur_model())

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
    self.tool_box.grid(column = 1, row = 0, sticky = sticky_all)
    self.quitButton.grid(column = 0, row = 1, columnspan = 1, sticky = sticky_all)

  def get_brush(self):
    if self.tool_box == None:
      return None
    else:
      return self.tool_box.get_brush()

  def get_current_model(self):
    pass

  def get_models(self):
    pass

  def get_clipboard(self):
    return self.clipboard_layer

  def update_design_box(self):
    model = self.tool_box.get_model()
    self.design_box.switch_model(model)

  def export_data(self, path):
    models = self.tool_box.get_models()
    copies = self.tool_box.get_copies()

    if path.endswith(".xml"):
      rbd_io.export_xml(path, models, copies)
      print "XML output written to", path
    elif path.endswith(".rbd"):
      particle_specs = self.tool_box.brush_box.particle_buttons.objects
      body_specs = self.tool_box.brush_box.body_buttons.objects
      rbd_io.export_rbd(path, models, particle_specs, body_specs)
      print ".rbd output written to", path
    else:
      print "Bad output path:", path

  def import_data(self):
    path = tkFileDialog.askopenfilename(title = "Choose import path...", defaultextension=".rbd", filetypes=[("RBD", "*.rbd"), ("All files", "*")])
    rbd_io.import_rbd(path, self)

  def cancel_operation(self):
    self.design_box.canvas.current_operation.cancel()
    
  def handle_focus(self, event):
    focus_allowed = ['Entry']
    if event.widget.winfo_class() not in focus_allowed:
      self.design_box.canvas.focus_set()
    print event.widget.winfo_class(), self.focus_get()




app = Application()


app.master.title('Rigid Body Designer')

app.mainloop()
app.quit()
