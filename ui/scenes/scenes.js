// The desktop scenes, made by design/make_scenes.py (the pictures; ui/ambient.js adds the small things that move).
// labels: text from your real data (deskfacts.py), drawn over the picture. viz: where his ring sits.
window.SCENES = {
 "bench": {
  "title": "Drafting bench",
  "viz": [
   0.5,
   0.49074074074074076
  ],
  "size": [
   3840,
   2160
  ],
  "labels": [
   {
    "k": "checked",
    "tpl": "Checked: {address}",
    "attrs": {
     "x": "804",
     "y": "2038",
     "fill": "#a9d4ff",
     "fill-opacity": ".7",
     "font-size": "24",
     "font-family": "'IBM Plex Mono',Consolas,monospace"
    }
   },
   {
    "k": "rev",
    "tpl": "listening core, rev. {rev}",
    "attrs": {
     "x": "280",
     "y": "296",
     "fill": "#a9d4ff",
     "fill-opacity": ".6",
     "font-size": "28",
     "font-family": "'IBM Plex Mono',Consolas,monospace"
    }
   },
   {
    "k": "fix",
    "tpl": "{fix}",
    "attrs": {
     "x": "3080",
     "y": "820",
     "fill": "#a9d4ff",
     "fill-opacity": ".65",
     "font-size": "32",
     "font-family": "'Segoe Print','Bradley Hand','Comic Sans MS',cursive"
    }
   }
  ],
  "defaults": {
   "rev": "27",
   "fix": "the old bearing squeaked. replaced 11/05",
   "address": "you"
  },
  "bg": "#0b1b2e",
  "ink": "#a9d4ff",
  "accent": "#ffb347",
  "panel": "rgba(9,24,42,.9)",
  "border": "rgba(169,212,255,.5)",
  "text": "#e7f2ff",
  "dim": "#9cb7d3",
  "style": "sheet",
  "ring": 0.15
 },
 "station": {
  "title": "Orbital station",
  "viz": [
   0.5,
   0.4537037037037037
  ],
  "size": [
   3840,
   2160
  ],
  "labels": [
   {
    "k": "orbit",
    "tpl": "ORBIT {days}{night}",
    "attrs": {
     "x": "3200",
     "y": "120",
     "fill": "#8fd8ff",
     "fill-opacity": ".8",
     "font-size": "36",
     "letter-spacing": "8",
     "text-anchor": "end",
     "font-family": "Rajdhani,'Bahnschrift','Segoe UI',sans-serif",
     "font-weight": "600"
    }
   }
  ],
  "defaults": {
   "days": "1",
   "night": ""
  },
  "bg": "#03060c",
  "ink": "#8fd8ff",
  "accent": "#7fe7ff",
  "panel": "rgba(8,16,30,.86)",
  "border": "rgba(143,216,255,.45)",
  "text": "#eaf6ff",
  "dim": "#9bb6cc",
  "style": "module",
  "ring": 0.12
 },
 "archive": {
  "title": "The archive",
  "viz": [
   0.5,
   0.38425925925925924
  ],
  "size": [
   3840,
   2160
  ],
  "labels": [
   {
    "k": "plate",
    "tpl": "The catalogue: {memories} cards  ·  {routines} routines  ·  kept since {since}",
    "attrs": {
     "x": "1920",
     "y": "2098",
     "fill": "#f3e2b8",
     "fill-opacity": ".85",
     "font-size": "34",
     "text-anchor": "middle",
     "font-style": "italic",
     "font-family": "'Cormorant Garamond',Georgia,serif"
    }
   }
  ],
  "defaults": {
   "memories": "0",
   "routines": "0",
   "since": "today"
  },
  "bg": "#0a0806",
  "ink": "#e8d3a8",
  "accent": "#7fd6ff",
  "panel": "rgba(28,22,15,.93)",
  "border": "rgba(200,164,106,.55)",
  "text": "#f3e9d6",
  "dim": "#b8a68a",
  "style": "card",
  "ring": 0.11
 },
 "signal": {
  "title": "Listening post",
  "viz": [
   0.5,
   0.46296296296296297
  ],
  "size": [
   3840,
   2160
  ],
  "labels": [
   {
    "k": "ch",
    "tpl": "CH1 VOICE      CH2 HOUSE {house}      CH3 NETWORK {net}",
    "attrs": {
     "x": "240",
     "y": "96",
     "fill": "#5dffc8",
     "fill-opacity": ".75",
     "font-size": "36",
     "font-family": "'Share Tech Mono','Cascadia Mono',Consolas,monospace"
    }
   }
  ],
  "defaults": {
   "house": "",
   "net": ""
  },
  "bg": "#03100d",
  "ink": "#5dffc8",
  "accent": "#ffcf5d",
  "panel": "rgba(3,20,16,.9)",
  "border": "rgba(93,255,200,.45)",
  "text": "#d9fff1",
  "dim": "#8fc7b4",
  "style": "scope",
  "ring": 0.14
 },
 "chart": {
  "title": "Cartographer",
  "viz": [
   0.46875,
   0.5092592592592593
  ],
  "size": [
   3840,
   2160
  ],
  "labels": [
   {
    "k": "p1",
    "tpl": "{p1}",
    "attrs": {
     "x": "1080",
     "y": "820",
     "fill": "#e6f7f1",
     "fill-opacity": ".8",
     "font-size": "44",
     "font-style": "italic",
     "font-family": "Fraunces,'Cambria',Georgia,serif"
    }
   },
   {
    "k": "p2",
    "tpl": "{p2}",
    "attrs": {
     "x": "2080",
     "y": "1420",
     "fill": "#e6f7f1",
     "fill-opacity": ".8",
     "font-size": "44",
     "font-style": "italic",
     "font-family": "Fraunces,'Cambria',Georgia,serif"
    }
   },
   {
    "k": "p3",
    "tpl": "{p3}",
    "attrs": {
     "x": "1560",
     "y": "600",
     "fill": "#e6f7f1",
     "fill-opacity": ".8",
     "font-size": "46",
     "font-style": "italic",
     "font-family": "Fraunces,'Cambria',Georgia,serif"
    }
   },
   {
    "k": "p4",
    "tpl": "{p4}",
    "attrs": {
     "x": "2420",
     "y": "760",
     "fill": "#e6f7f1",
     "fill-opacity": ".8",
     "font-size": "40",
     "font-style": "italic",
     "font-family": "Fraunces,'Cambria',Georgia,serif"
    }
   }
  ],
  "defaults": {
   "p1": "Render Ridge",
   "p2": "Queue Basin",
   "p3": "Mount Inbox",
   "p4": "Patchnote Shoals"
  },
  "bg": "#071a1e",
  "ink": "#9fe3d6",
  "accent": "#ff9f5a",
  "panel": "rgba(6,28,32,.9)",
  "border": "rgba(159,227,214,.5)",
  "text": "#eafaf6",
  "dim": "#9cc4bc",
  "style": "legend",
  "ring": 0.1
 },
 "greenhouse": {
  "title": "Greenhouse",
  "viz": [
   0.5,
   0.4537037037037037
  ],
  "size": [
   3840,
   2160
  ],
  "labels": [
   {
    "k": "streak",
    "tpl": "watered {days} days",
    "attrs": {
     "x": "420",
     "y": "1850",
     "fill": "#dfe8e2",
     "fill-opacity": ".75",
     "font-size": "36",
     "font-family": "'Segoe Print','Bradley Hand','Comic Sans MS',cursive"
    }
   },
   {
    "k": "outside",
    "tpl": "outside: {temp}",
    "attrs": {
     "x": "420",
     "y": "1910",
     "fill": "#dfe8e2",
     "fill-opacity": ".7",
     "font-size": "36",
     "font-family": "'Segoe Print','Bradley Hand','Comic Sans MS',cursive"
    }
   },
   {
    "k": "planted",
    "tpl": "planted {planted}",
    "attrs": {
     "x": "420",
     "y": "1965",
     "fill": "#dfe8e2",
     "fill-opacity": ".55",
     "font-size": "30",
     "font-family": "'Segoe Print','Bradley Hand','Comic Sans MS',cursive"
    }
   },
   {
    "k": "t1",
    "tpl": "{t1}",
    "attrs": {
     "x": "2700",
     "y": "1600",
     "fill": "#2a2a20",
     "font-size": "24",
     "font-family": "'IBM Plex Mono',Consolas,monospace"
    }
   },
   {
    "k": "t2",
    "tpl": "{t2}",
    "attrs": {
     "x": "3020",
     "y": "1600",
     "fill": "#2a2a20",
     "font-size": "24",
     "font-family": "'IBM Plex Mono',Consolas,monospace"
    }
   },
   {
    "k": "t3",
    "tpl": "{t3}",
    "attrs": {
     "x": "3340",
     "y": "1600",
     "fill": "#2a2a20",
     "font-size": "24",
     "font-family": "'IBM Plex Mono',Consolas,monospace"
    }
   }
  ],
  "defaults": {
   "days": "12",
   "temp": "18°",
   "planted": "the first night",
   "t1": "basil",
   "t2": "fern no. 3",
   "t3": "stubborn one"
  },
  "bg": "#06100c",
  "ink": "#b9f0c8",
  "accent": "#ffc46b",
  "panel": "rgba(8,20,15,.9)",
  "border": "rgba(185,240,200,.45)",
  "text": "#eafaf0",
  "dim": "#9fbfa9",
  "style": "card",
  "ring": 0.12
 }
};
