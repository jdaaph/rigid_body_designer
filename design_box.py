import Tkinter as tk
import ttk
import itertools as it

sticky_all = tk.N + tk.S + tk.E + tk.W

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

  def switch_model(self, new_canvas):
    if self.canvas != None:
      self.canvas.grid_forget()
    new_canvas.grid(row = 0, column = 0, sticky = sticky_all)
    self.canvas = new_canvas

    self.xscrollbar['command'] = self.canvas.xview
    self.yscrollbar['command'] = self.canvas.yview
    self.canvas.config(xscrollcommand = self.xscrollbar.set, yscrollcommand = self.yscrollbar.set)
