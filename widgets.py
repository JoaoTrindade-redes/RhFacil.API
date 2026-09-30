"""Widgets reutilizáveis do RH Fácil.

Mantém máscaras e componentes de entrada separados da tela principal.
"""
import tkinter as tk
import customtkinter as ctk
from validacoes import only_digits

FONT_INPUT=("Segoe UI",15)
TEXT="#202326"

class SegmentedField(ctk.CTkFrame):
    def __init__(self,master,variable,sizes,separators,placeholder=None,command=None):
        super().__init__(master,fg_color="transparent")
        self.variable=variable; self.parts=[]; self.command=command
        digits=only_digits(variable.get()); offset=0
        for i,size in enumerate(sizes):
            part=tk.StringVar(value=digits[offset:offset+size]); offset+=size
            self.parts.append(part)
            entry=ctk.CTkEntry(self,textvariable=part,width=max(52,size*17+16),height=44,justify="center",font=FONT_INPUT,fg_color="#eef1f3",border_color="#aeb6bd")
            entry.pack(side="left")
            part.trace_add("write",lambda *_a,idx=i,lim=size:self._sync(idx,lim))
            if i<len(separators):
                ctk.CTkLabel(self,text=separators[i],text_color=TEXT,font=("Segoe UI",18,"bold")).pack(side="left",padx=5)
        self.widgets=[w for w in self.winfo_children() if isinstance(w,ctk.CTkEntry)]
        self._sync_all()
    def _sync(self,idx,lim):
        v=self.parts[idx]; clean=only_digits(v.get())[:lim]
        if v.get()!=clean: v.set(clean); return
        self._sync_all()
        if len(clean)==lim and idx+1<len(self.widgets): self.widgets[idx+1].focus_set()
        if self.command: self.command()
    def _sync_all(self): self.variable.set("".join(p.get() for p in self.parts))
    def focus_set(self):
        if self.widgets: self.widgets[0].focus_set()

class PhoneField(ctk.CTkFrame):
    def __init__(self,master,variable,command=None):
        super().__init__(master,fg_color="transparent")
        self.variable=variable; self.command=command
        raw=only_digits(variable.get())[:11]
        self.ddd=tk.StringVar(value=raw[:2]); self.p1=tk.StringVar(value=raw[2:7]); self.p2=tk.StringVar(value=raw[7:11]); self._busy=False
        ctk.CTkLabel(self,text="(",text_color=TEXT,font=("Segoe UI",18,"bold")).pack(side="left")
        self.e1=ctk.CTkEntry(self,textvariable=self.ddd,width=54,height=44,justify="center",font=FONT_INPUT,fg_color="#eef1f3",border_color="#aeb6bd"); self.e1.pack(side="left")
        ctk.CTkLabel(self,text=")",text_color=TEXT,font=("Segoe UI",18,"bold")).pack(side="left",padx=(2,8))
        self.e2=ctk.CTkEntry(self,textvariable=self.p1,width=92,height=44,justify="center",font=FONT_INPUT,fg_color="#eef1f3",border_color="#aeb6bd"); self.e2.pack(side="left")
        ctk.CTkLabel(self,text="-",text_color=TEXT,font=("Segoe UI",18,"bold")).pack(side="left",padx=6)
        self.e3=ctk.CTkEntry(self,textvariable=self.p2,width=78,height=44,justify="center",font=FONT_INPUT,fg_color="#eef1f3",border_color="#aeb6bd"); self.e3.pack(side="left")
        self.ddd.trace_add("write",lambda *_:self._sync(self.ddd,2,self.e2)); self.p1.trace_add("write",lambda *_:self._sync(self.p1,5,self.e3)); self.p2.trace_add("write",lambda *_:self._sync(self.p2,4,None)); self._write_value()
    def _sync(self,var,limit,next_widget):
        if self._busy:return
        self._busy=True
        try:
            clean=only_digits(var.get())[:limit]
            if var.get()!=clean: var.set(clean)
            self._write_value()
        finally:self._busy=False
        if len(var.get())==limit and next_widget is not None: next_widget.focus_set()
    def _write_value(self):
        self.variable.set(self.ddd.get()+self.p1.get()+self.p2.get())
        if self.command:self.command()
    def focus_set(self): self.e1.focus_set()

class YesNoField(ctk.CTkFrame):
    def __init__(self,master,variable,command=None):
        super().__init__(master,fg_color="transparent")
        self.sim=ctk.CTkRadioButton(self,text="Sim",variable=variable,value="Sim",command=command,text_color=TEXT,fg_color="#4e5358",hover_color="#3f4448",font=("Segoe UI",14,"bold"),radiobutton_width=22,radiobutton_height=22)
        self.nao=ctk.CTkRadioButton(self,text="Não",variable=variable,value="Não",command=command,text_color=TEXT,fg_color="#4e5358",hover_color="#3f4448",font=("Segoe UI",14,"bold"),radiobutton_width=22,radiobutton_height=22)
        self.sim.pack(side="left",padx=(0,24)); self.nao.pack(side="left")

class MoneyField(ctk.CTkFrame):
    def __init__(self,master,variable):
        super().__init__(master,fg_color="transparent"); self.variable=variable
        ctk.CTkLabel(self,text="R$",text_color=TEXT,font=("Segoe UI",15,"bold")).pack(side="left",padx=(0,8))
        raw=only_digits(variable.get().split(",")[0]); self.reais=tk.StringVar(value=raw)
        self.entry=ctk.CTkEntry(self,textvariable=self.reais,height=44,width=150,font=FONT_INPUT,justify="right",fg_color="#eef1f3",border_color="#aeb6bd"); self.entry.pack(side="left")
        ctk.CTkLabel(self,text=",00",text_color=TEXT,font=("Segoe UI",15,"bold")).pack(side="left",padx=(4,0)); self.reais.trace_add("write",self.sync); self.sync()
    def sync(self,*_):
        raw=only_digits(self.reais.get())[:9]
        if self.reais.get()!=raw:self.reais.set(raw); return
        self.variable.set(f"R$ {raw},00" if raw else "")

class MeasureField(ctk.CTkFrame):
    def __init__(self,master,variable,unit,decimals=1,whole_limit=3):
        super().__init__(master,fg_color="transparent"); self.variable=variable; self.unit=unit; self.decimals=decimals
        raw=variable.get().replace(unit,"").strip().replace(".",","); parts=raw.split(",")
        self.a=tk.StringVar(value=only_digits(parts[0] if parts else "")[:whole_limit]); self.b=tk.StringVar(value=only_digits(parts[1] if len(parts)>1 else "")[:decimals])
        self.e1=ctk.CTkEntry(self,textvariable=self.a,width=75,height=44,font=FONT_INPUT,justify="center",fg_color="#eef1f3",border_color="#aeb6bd"); self.e1.pack(side="left")
        ctk.CTkLabel(self,text=",",text_color=TEXT,font=("Segoe UI",18,"bold")).pack(side="left",padx=5)
        self.e2=ctk.CTkEntry(self,textvariable=self.b,width=55,height=44,font=FONT_INPUT,justify="center",fg_color="#eef1f3",border_color="#aeb6bd"); self.e2.pack(side="left")
        ctk.CTkLabel(self,text=unit,text_color=TEXT,font=("Segoe UI",14,"bold")).pack(side="left",padx=8)
        self.a.trace_add("write",self.sync); self.b.trace_add("write",self.sync); self.sync()
    def sync(self,*_):
        a=only_digits(self.a.get())[:3]; b=only_digits(self.b.get())[:self.decimals]
        if self.a.get()!=a:self.a.set(a); return
        if self.b.get()!=b:self.b.set(b); return
        self.variable.set(f"{a},{b} {self.unit}" if a or b else "")
