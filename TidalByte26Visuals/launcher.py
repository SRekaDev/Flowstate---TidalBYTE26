"""Flowstate's thermal-gradient launcher."""
import tkinter as tk
from tkinter import ttk
from math import exp
from PIL import Image, ImageTk

NIGHT = '#101420'


def build(app, frame):
    canvas = tk.Canvas(frame, bg=NIGHT, highlightthickness=0)
    canvas.pack(fill='both', expand=True)
    pixels = []
    for y in range(100):
        for x in range(180):
            cool = exp(-((x-4)/17)**2-((y-52)/24)**2)
            warm = exp(-((x-176)/17)**2-((y-52)/24)**2)
            pixels.append((int(16+9*cool+66*warm),int(20+49*cool+29*warm),int(32+50*cool+4*warm)))
    field = Image.new('RGB',(180,100))
    field.putdata(pixels)
    style = ttk.Style(frame)
    style.configure('Thermal.TButton',background='#283040',foreground='#edf2fa',
                    anchor='center',padding=(12,9),font=('Lexend',12,'normal'),borderwidth=1,relief='flat')
    style.map('Thermal.TButton',background=[('disabled','#191e2b'),('pressed','#374250'),
              ('active','#384653'),('focus','#323f50')],foreground=[('disabled','#798398')])
    controls = tk.Frame(canvas,bg=NIGHT)
    controls.place(relx=.5,rely=.61,anchor='center')
    app.dot_images=[]
    def button(parent,label,action,color):
        def dot(core,halo):
            pic=tk.PhotoImage(width=14,height=14)
            for y in range(14):
                for x in range(14):
                    radius=(x-6.5)**2+(y-6.5)**2
                    if radius<29:
                        pic.put(core if radius<8 else halo,to=(x,y))
            app.dot_images.append(pic)
            return pic
        normal=dot(color,'#384451')
        bright=dot('#ffffff',color)
        dim=dot('#637080','#2c3441')
        return ttk.Button(parent,text=label,command=action,style='Thermal.TButton',compound='left',
                          image=(normal,'disabled',dim,'active',bright,'focus',bright))
    app.action=button(controls,'Begin session',app.start,'#79e7dd')
    app.action.pack(pady=(0,12))
    row=tk.Frame(controls,bg=NIGHT)
    row.pack(anchor='center')
    app.sample=button(row,'Example report',app.preview,'#8de6e2')
    app.latest=button(row,'Last session',app.open_latest,'#ffc98c')
    app.camera_button=button(row,'Webcam',app.show_camera,'#91d3cb')
    app.past_sessions=button(row,'Past sessions',app.open_past_session,'#ffc98c')
    for col,item in enumerate((app.sample,app.latest,app.past_sessions,app.camera_button)):
        row.columnconfigure(col,weight=1,uniform='buttons')
        item.grid(row=0,column=col,padx=4,sticky='ew')
    style.configure('Thermal.TCheckbutton',font=('Lexend',11,'normal'),background=NIGHT,foreground='#edf2fa')
    app.ai_box=ttk.Checkbutton(controls,style='Thermal.TCheckbutton',text='Add a local Nemotron review',variable=app.ai)
    app.ai_box.pack(pady=(6,0))
    def paint(event):
        w,h=event.width,event.height
        canvas.delete('art')
        canvas.field=ImageTk.PhotoImage(field.resize((w,h),Image.Resampling.BILINEAR))
        canvas.create_image(0,0,anchor='nw',image=canvas.field,tags='art')
        def text(x,y,value,size,color,anchor='center'):
            return canvas.create_text(x,y,text=value,font=('Lexend',size,'normal'),fill=color,anchor=anchor,tags='art')
        canvas.create_rectangle(12,12,w-12,h-12,outline='#41444b',tags='art')
        canvas.create_image(32,39,image=app.brand,anchor='w',tags='art')
        brand=text(32+app.brand.width()+8,39,'Flowstate',19,'#dae3f0','w')
        edge=canvas.bbox(brand)[2]+5
        canvas.create_oval(edge,33,edge+6,39,fill='#77efc2',outline='',tags='art')
        text(w/2,h*.29,'THERMAL EQUILIBRIUM',11,'#9aa8bc')
        text(w/2,h*.37,app.heading.get(),34,'#edf1fb')
        for i in range(100):
            color='#%02x%02x%02x'%(int(90+163*i/99),int(229-63*i/99),int(237-149*i/99))
            canvas.create_line(w*(.22+.0056*i),h*.465,w*(.22+.0056*(i+1))+1,h*.465,fill=color,width=2,tags='art')
        x,y=w*.63,h*.465
        canvas.create_polygon(x-6,y,x,y-6,x+6,y,x,y+6,fill='#ffd598',outline='#e4ac73',tags='art')
        canvas.create_text(w/2,h*.84,text=app.message.get(),width=w*.72,justify='center',
                           font=('Lexend',12,'normal'),fill='#afbbce',tags='art')
    canvas.bind('<Configure>',paint)
    def refresh(*_):
        canvas.event_generate('<Configure>',width=canvas.winfo_width(),height=canvas.winfo_height())
    app.message.trace_add('write',refresh)
    app.heading.trace_add('write',refresh)
