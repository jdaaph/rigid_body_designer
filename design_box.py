import Tkinter as tk
import ttk
import itertools as it

sticky_all = tk.N + tk.S + tk.E + tk.W

from model_canvas import ModelCanvas
import utils

class DesignBox(tk.Frame):
  # canvas is the model....
  canvas = None
  xscrollbar = None
  yscrollbar = None
  def __init__(self, master):
    tk.Frame.__init__(self, master)

    self.rowconfigure(0, weight = 1)
    self.columnconfigure(0, weight = 1)

    ## Add scrollbars for canvas
    self.xscrollbar = tk.Scrollbar(self, orient = tk.HORIZONTAL)
    self.xscrollbar.grid(row = 1, column = 0, sticky = sticky_all)
    self.yscrollbar = tk.Scrollbar(self, orient = tk.VERTICAL)
    self.yscrollbar.grid(row = 0, column = 1, sticky = sticky_all)

    self.canvas = ModelCanvas(self, mode = 'edit')
    self.canvas.grid(row = 0, column = 0, sticky = sticky_all)

    self.xscrollbar['command'] = self.canvas.xview
    self.yscrollbar['command'] = self.canvas.yview
    self.canvas.config(xscrollcommand = self.xscrollbar.set, yscrollcommand = self.yscrollbar.set)

    ## Set up event handlers
    self.bind_all('<<ModelSelect>>', self.handle_model_select)

  def switch_model(self, model):
    self.canvas.set_model(model)

  def handle_model_select(self, event):
    print 'modelselect'
    model = utils.event_data_retrieve(event.state)
    self.switch_model(model)
