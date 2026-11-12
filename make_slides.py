"""Build an editable PowerPoint overview of the brooder-control project."""

from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
PHOTO = ROOT / "webapp" / "static" / "chicks-in-brooder.jpg"
OUTPUT = ROOT / "Smart_Brooder_Project_Slides.pptx"

PAGE_W, PAGE_H = 13.333, 7.5
FONT = "Aptos"
NAVY = RGBColor(20, 35, 56)
INK = RGBColor(28, 43, 62)
MUTED = RGBColor(91, 109, 132)
BLUE = RGBColor(31, 111, 235)
TEAL = RGBColor(37, 145, 128)
ORANGE = RGBColor(222, 117, 41)
GREEN = RGBColor(35, 126, 82)
BG = RGBColor(245, 248, 252)
WHITE = RGBColor(255, 255, 255)
PALE_BLUE = RGBColor(232, 241, 254)
PALE_GREEN = RGBColor(231, 245, 237)
PALE_ORANGE = RGBColor(255, 242, 226)
BORDER = RGBColor(221, 229, 239)
DARK_BG = RGBColor(16, 25, 39)
DARK_MUTED = RGBColor(202, 215, 231)


def add_text(slide, text, x, y, w, h, size=16, color=INK, bold=False,
             align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.TOP, italic=False):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = Inches(0)
    frame.margin_right = Inches(0)
    frame.margin_top = Inches(0)
    frame.margin_bottom = Inches(0)
    frame.vertical_anchor = valign
    lines = text.splitlines() or [""]
    for index, line in enumerate(lines):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.alignment = align
        paragraph.space_after = Pt(0)
        run = paragraph.add_run()
        run.text = line
        run.font.name = FONT
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.italic = italic
        run.font.color.rgb = color
    return box


def add_card(slide, x, y, w, h, fill=WHITE, line=BORDER):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = line
    shape.line.width = Pt(0.8)
    return shape


def add_picture_fit(slide, path, x, y, w, h):
    with Image.open(path) as image:
        image_ratio = image.width / image.height
    box_ratio = w / h
    if image_ratio > box_ratio:
        picture_w = w
        picture_h = w / image_ratio
    else:
        picture_h = h
        picture_w = h * image_ratio
    left = x + (w - picture_w) / 2
    top = y + (h - picture_h) / 2
    return slide.shapes.add_picture(
        str(path), Inches(left), Inches(top), width=Inches(picture_w), height=Inches(picture_h)
    )


def add_image_card(slide, path, x, y, w, h):
    add_card(slide, x, y, w, h)
    add_picture_fit(slide, path, x + 0.1, y + 0.1, w - 0.2, h - 0.2)


def add_bullet(slide, text, x, y, w, size=14, color=INK, dot_color=BLUE):
    dot = slide.shapes.add_shape(
        MSO_SHAPE.OVAL, Inches(x), Inches(y + 0.1), Inches(0.1), Inches(0.1)
    )
    dot.fill.solid()
    dot.fill.fore_color.rgb = dot_color
    dot.line.fill.background()
    add_text(slide, text, x + 0.22, y, w - 0.22, 0.56, size=size, color=color)


def add_metric(slide, x, y, w, label, value, note, accent=BLUE):
    add_card(slide, x, y, w, 1.24, fill=WHITE)
    add_text(slide, label.upper(), x + 0.18, y + 0.14, w - 0.36, 0.2,
             size=9, color=MUTED, bold=True)
    add_text(slide, value, x + 0.18, y + 0.4, w - 0.36, 0.38,
             size=21, color=accent, bold=True)
    add_text(slide, note, x + 0.18, y + 0.86, w - 0.36, 0.28,
             size=10, color=MUTED)


def add_header(slide, kicker, title, subtitle="", number=None):
    add_text(slide, kicker.upper(), 0.68, 0.25, 8.5, 0.22, size=9, color=BLUE, bold=True)
    add_text(slide, title, 0.68, 0.55, 12.0, 0.52, size=27, color=NAVY, bold=True)
    if subtitle:
        add_text(slide, subtitle, 0.7, 1.12, 12.0, 0.32, size=12, color=MUTED)
    if number is not None:
        add_text(slide, "SMART BROODER  |  PROJECT 14", 0.68, 7.12, 8, 0.18,
                 size=8, color=MUTED)
        add_text(slide, f"{number:02d}", 12.15, 7.1, 0.5, 0.2,
                 size=9, color=MUTED, align=PP_ALIGN.RIGHT)


def add_arrow(slide, x, y, w=0.38, h=0.32, color=BLUE):
    arrow = slide.shapes.add_shape(
        MSO_SHAPE.RIGHT_ARROW, Inches(x), Inches(y), Inches(w), Inches(h)
    )
    arrow.fill.solid()
    arrow.fill.fore_color.rgb = color
    arrow.line.fill.background()


def new_slide(presentation):
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = BG
    return slide


def add_step_card(slide, x, y, w, step, title, body, accent=BLUE):
    add_card(slide, x, y, w, 1.3, fill=WHITE)
    add_text(slide, step, x + 0.18, y + 0.16, 0.35, 0.28, size=17, color=accent, bold=True)
    add_text(slide, title, x + 0.62, y + 0.14, w - 0.78, 0.28, size=13, color=INK, bold=True)
    add_text(slide, body, x + 0.18, y + 0.54, w - 0.36, 0.58, size=11, color=MUTED)


def build_deck():
    required = [
        PHOTO,
        RESULTS / "fig2_controllers.png",
        RESULTS / "fig3_capacity.png",
        RESULTS / "fig6_windup.png",
        RESULTS / "fig7_numerics.png",
    ]
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Required slide asset(s) are missing: " + ", ".join(map(str, missing)))

    presentation = Presentation()
    presentation.slide_width = Inches(PAGE_W)
    presentation.slide_height = Inches(PAGE_H)
    presentation.core_properties.title = "Smart Incubator / Brooder Controller"
    presentation.core_properties.subject = "Project overview, thermal model, experiments and web application"
    presentation.core_properties.keywords = "brooder, incubator, PI, PID, Flask, Euler, RK4"

    # 1. Title
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = DARK_BG
    add_text(slide, "PROJECT 14  •  ENGINEERING OVERVIEW", 0.8, 0.9, 5.9, 0.28,
             size=10, color=RGBColor(139, 191, 255), bold=True)
    add_text(slide, "Smart Incubator /\nBrooder Controller", 0.8, 1.65, 6.0, 1.65,
             size=34, color=WHITE, bold=True)
    add_text(slide, "From thermal equations to a beginner-friendly web simulation", 0.82, 3.55,
             5.7, 0.72, size=18, color=DARK_MUTED)
    add_text(slide, "PI/PID control  •  Euler and RK4  •  Flask + Pygame", 0.82, 4.55,
             5.8, 0.35, size=12, color=RGBColor(139, 191, 255), bold=True)
    add_card(slide, 7.15, 0.82, 5.35, 5.55, fill=RGBColor(28, 43, 62), line=RGBColor(63, 82, 106))
    add_picture_fit(slide, PHOTO, 7.3, 0.97, 5.05, 5.05)
    add_text(slide, "Real brooder photo • ELTORO.VET • CC0", 7.25, 6.48, 5.1, 0.24,
             size=9, color=DARK_MUTED, align=PP_ALIGN.RIGHT)
    add_text(slide, "A learning model—not a real brooder controller.", 0.82, 6.8,
             6.0, 0.24, size=10, color=DARK_MUTED)

    # 2. Problem and goal
    slide = new_slide(presentation)
    add_header(slide, "01  |  The challenge", "Why model a brooder?",
               "Temperature is affected by weather, insulation, chick heat and a heater with a finite capacity.", 2)
    cards = [
        ("WEATHER", "Cold nights and rain increase heat loss.", PALE_BLUE, BLUE),
        ("HEATER LIMIT", "A heater can add heat, but cannot cool or exceed its power rating.", PALE_ORANGE, ORANGE),
        ("CHICK COMFORT", "The model tracks whether the target and comfort band can be maintained.", PALE_GREEN, GREEN),
    ]
    for i, (label, body, fill, accent) in enumerate(cards):
        x = 0.68 + i * 4.12
        add_card(slide, x, 1.7, 3.85, 1.65, fill=fill, line=fill)
        add_text(slide, label, x + 0.22, 1.92, 3.4, 0.22, size=10, color=accent, bold=True)
        add_text(slide, body, x + 0.22, 2.28, 3.4, 0.78, size=16, color=INK, bold=True)
    add_text(slide, "The question", 0.72, 3.85, 2.2, 0.25, size=12, color=BLUE, bold=True)
    add_text(slide, "Can feedback control keep the brooder near 35 °C when conditions change?",
             0.72, 4.18, 11.6, 0.55, size=23, color=NAVY, bold=True)
    add_card(slide, 0.68, 5.15, 12.0, 1.1, fill=WHITE)
    add_text(slide, "PROJECT GOAL", 0.9, 5.38, 1.55, 0.25, size=10, color=GREEN, bold=True)
    add_text(slide, "Make the physics, controller response and practical limits visible to learners.",
             2.48, 5.32, 9.9, 0.45, size=17, color=INK, bold=True)

    # 3. Physical model
    slide = new_slide(presentation)
    add_header(slide, "02  |  Thermal model", "Follow the heat",
               "A single well-mixed temperature represents the air and bedding inside the brooder.", 3)
    add_card(slide, 0.68, 1.62, 12.0, 1.12, fill=PALE_BLUE, line=PALE_BLUE)
    add_text(slide, "C dT/dt = P + Q_chicks - [(1 + k_rain · rain(t)) / R] · (T - T_a(t))",
             0.95, 1.92, 11.45, 0.48, size=20, color=NAVY, bold=True, align=PP_ALIGN.CENTER,
             valign=MSO_ANCHOR.MIDDLE)
    variables = [
        ("C", "Thermal capacity: how quickly the enclosure warms or cools."),
        ("P", "Delivered heater power, clipped between 0 and P_max."),
        ("Q_chicks", "Metabolic heat from chicks; default total is 8 W."),
        ("R", "Insulation resistance; larger R means less heat loss."),
        ("T_a, rain", "Weather inputs; rain raises the heat-loss rate."),
        ("T_set", "Controller target: 35 °C in the example configuration."),
    ]
    for i, (term, explanation) in enumerate(variables):
        col, row = i % 2, i // 2
        x, y = 0.72 + col * 4.2, 3.0 + row * 0.82
        add_text(slide, term, x, y, 1.15, 0.25, size=13, color=BLUE, bold=True)
        add_text(slide, explanation, x + 1.2, y - 0.02, 2.8, 0.58, size=11, color=INK)
    add_card(slide, 9.25, 3.03, 3.35, 2.75, fill=WHITE)
    add_text(slide, "DEFAULT EXAMPLE", 9.48, 3.25, 2.9, 0.25, size=10, color=GREEN, bold=True)
    add_text(slide, "C = 8,000 J/K\nR = 0.20 K/W\nP_max = 150 W\nQ_chicks = 8 W\nk_rain = 0.30",
             9.48, 3.68, 2.9, 1.7, size=15, color=INK)
    add_text(slide, "Simplifications: one temperature node; ideal sensor and heater; no humidity, ventilation or spatial gradients.",
             0.72, 5.85, 11.8, 0.46, size=11, color=MUTED, italic=True)

    # 4. Feedback and numerical solution
    slide = new_slide(presentation)
    add_header(slide, "03  |  Control loop", "Feedback turns temperature error into heater power",
               "The model integrates both the brooder temperature and controller states at each time step.", 4)
    flow = [
        ("TARGET + SENSOR", "e = T_set - T"),
        ("P / PI / PID", "u = Kp·e + Ki·I − Kd·(T−Tm)/τd"),
        ("HEATER LIMIT", "P = clip(u, 0, P_max)"),
        ("THERMAL PLANT", "temperature changes"),
        ("FEEDBACK", "measure T again"),
    ]
    start_x, card_w, gap = 0.68, 2.0, 0.48
    for i, (label, body) in enumerate(flow):
        x = start_x + i * (card_w + gap)
        add_card(slide, x, 1.75, card_w, 1.45, fill=WHITE)
        add_text(slide, label, x + 0.14, 1.98, card_w - 0.28, 0.23,
                 size=9, color=BLUE if i < 3 else GREEN, bold=True, align=PP_ALIGN.CENTER)
        add_text(slide, body, x + 0.13, 2.36, card_w - 0.26, 0.54,
                 size=12, color=INK, bold=True, align=PP_ALIGN.CENTER)
        if i < len(flow) - 1:
            add_arrow(slide, x + card_w + 0.07, 2.3, 0.32, 0.3)
    control_cards = [
        ("P", "Simple response; steady load can leave a temperature offset.", BLUE),
        ("PI", "Integral action removes steady error when the heater has enough capacity.", TEAL),
        ("PID", "Derivative action anticipates trends; it adds little for this slow first-order plant.", ORANGE),
    ]
    for i, (label, body, accent) in enumerate(control_cards):
        x = 0.68 + i * 4.12
        add_card(slide, x, 3.78, 3.85, 1.45, fill=WHITE)
        add_text(slide, label, x + 0.2, 3.98, 0.6, 0.3, size=21, color=accent, bold=True)
        add_text(slide, body, x + 0.86, 3.96, 2.72, 0.93, size=12, color=INK)
    add_card(slide, 0.68, 5.65, 12.0, 0.68, fill=PALE_ORANGE, line=PALE_ORANGE)
    add_text(slide, "ANTI-WINDUP", 0.91, 5.86, 1.35, 0.22, size=10, color=ORANGE, bold=True)
    add_text(slide, "Back-calculation stops the integral term growing while the heater is saturated.",
             2.34, 5.78, 9.9, 0.36, size=14, color=INK)

    # 5. Solver validation
    slide = new_slide(presentation)
    add_header(slide, "04  |  Numerical validation", "The solver changes what the learner sees",
               "The left plot compares error against an exact PI reference; the right shows a stiff PID case.", 5)
    add_image_card(slide, RESULTS / "fig7_numerics.png", 0.68, 1.62, 12.0, 4.12)
    add_metric(slide, 0.68, 5.82, 5.8, "Maximum error at h = 300 s",
               "Euler 0.523 K", "RK4: 0.000433 K", accent=ORANGE)
    add_metric(slide, 6.88, 5.82, 5.8, "PID run at h = 100 s",
               "Euler oscillates", "RK4 stays close to the reference", accent=BLUE)

    # 6. Controller experiments
    slide = new_slide(presentation)
    add_header(slide, "05  |  Results", "Control choice changes recovery",
               "Cold night: ambient drops from 25 °C to 12 °C. Results use RK4 with h = 2 s.", 6)
    add_image_card(slide, RESULTS / "fig2_controllers.png", 0.68, 1.62, 7.55, 2.82)
    add_card(slide, 8.55, 1.62, 4.13, 2.82, fill=WHITE)
    add_text(slide, "WHAT THE PLOTS SHOW", 8.82, 1.9, 3.55, 0.25, size=10, color=GREEN, bold=True)
    add_bullet(slide, "P-only control cannot remove the steady load.", 8.82, 2.35, 3.5, size=12)
    add_bullet(slide, "Integral action removes steady error when power is sufficient.", 8.82, 3.1, 3.5, size=12)
    add_bullet(slide, "The derivative term adds little here and can amplify noise in real sensors.", 8.82, 3.85, 3.5, size=12)
    add_metric(slide, 0.68, 4.75, 3.83, "P-only steady error", "8.23 K", "cold-night case", accent=ORANGE)
    add_metric(slide, 4.78, 4.75, 3.83, "PI response", "2.77 K peak", "70 min recovery", accent=TEAL)
    add_metric(slide, 8.88, 4.75, 3.8, "Faster PI", "1.16 K peak", "45 min recovery", accent=BLUE)
    add_text(slide, "A controller cannot compensate for a heater that is too small or insulation that is too weak.",
             0.72, 6.32, 11.9, 0.32, size=12, color=NAVY, bold=True)

    # 7. Capacity, insulation and anti-windup
    slide = new_slide(presentation)
    add_header(slide, "06  |  Practical limits", "Capacity, insulation and anti-windup matter",
               "Tuning helps—but it cannot overcome an impossible heat balance.", 7)
    add_text(slide, "HEATER CAPACITY", 0.78, 1.55, 5.7, 0.22, size=10, color=BLUE, bold=True)
    add_text(slide, "INTEGRAL WINDUP", 6.92, 1.55, 5.7, 0.22, size=10, color=ORANGE, bold=True)
    add_image_card(slide, RESULTS / "fig3_capacity.png", 0.68, 1.86, 5.88, 2.25)
    add_image_card(slide, RESULTS / "fig6_windup.png", 6.78, 1.86, 5.9, 2.25)
    add_card(slide, 0.68, 4.28, 5.88, 1.3, fill=WHITE)
    add_text(slide, "At 12 °C with rain, about 141.5 W is needed. A 60 W or 100 W heater cannot hold 35 °C; 150 W can.",
             0.92, 4.57, 5.4, 0.75, size=13, color=INK)
    add_card(slide, 6.78, 4.28, 5.9, 1.3, fill=WHITE)
    add_text(slide, "With Ki = 0.05, anti-windup cuts start-up overshoot from 7.01 K to 2.70 K and settling from 85 to 56 min.",
             7.02, 4.57, 5.4, 0.75, size=13, color=INK)
    add_card(slide, 0.68, 5.82, 12.0, 0.62, fill=PALE_GREEN, line=PALE_GREEN)
    add_text(slide, "More insulation (R = 0.4 K/W) reduces required power to 49.5 W and gives 16 minutes of grace after heater failure.",
             0.91, 6.0, 11.5, 0.28, size=12, color=GREEN, bold=True)

    # 8. Application architecture
    slide = new_slide(presentation)
    add_header(slide, "07  |  Software architecture", "One simulation core, two ways to explore it",
               "The web app and Pygame interface use the same Python model and numerical solvers.", 8)
    modules = [
        ("BROWSER UI", "landing.html\nauth.html\nindex.html", PALE_BLUE, BLUE),
        ("FLASK APP", "routes\nvalidation\nCSRF + sessions", PALE_GREEN, GREEN),
        ("MODEL CORE", "model.py\nsolvers.py\nmetrics.py", PALE_ORANGE, ORANGE),
        ("SQLITE", "accounts\nsaved parameters\nresults + series", WHITE, NAVY),
    ]
    x_positions = [0.7, 3.75, 6.8, 9.85]
    for i, (title, body, fill, accent) in enumerate(modules):
        x = x_positions[i]
        add_card(slide, x, 1.9, 2.55, 2.25, fill=fill, line=fill if fill != WHITE else BORDER)
        add_text(slide, title, x + 0.18, 2.2, 2.2, 0.23, size=10, color=accent, bold=True, align=PP_ALIGN.CENTER)
        add_text(slide, body, x + 0.18, 2.65, 2.2, 1.1, size=13, color=INK, bold=True, align=PP_ALIGN.CENTER)
        if i < len(modules) - 1:
            add_arrow(slide, x + 2.62, 2.85, 0.35, 0.32)
    add_card(slide, 0.7, 4.6, 5.75, 1.25, fill=WHITE)
    add_text(slide, "WEB API", 0.95, 4.83, 1.15, 0.22, size=10, color=BLUE, bold=True)
    add_text(slide, "POST /api/simulate  •  GET /api/runs  •  load or delete a run by ID",
             2.08, 4.78, 4.1, 0.55, size=12, color=INK)
    add_card(slide, 6.75, 4.6, 5.65, 1.25, fill=WHITE)
    add_text(slide, "PYGAME", 7.0, 4.83, 1.0, 0.22, size=10, color=ORANGE, bold=True)
    add_text(slide, "Desktop GUI for live experiments; shares brooder/model.py and brooder/solvers.py.",
             8.0, 4.78, 4.1, 0.58, size=12, color=INK)
    add_text(slide, "The web app computes the run on the server, then the browser plays back the returned numerical states.",
             0.74, 6.12, 11.9, 0.34, size=12, color=NAVY, bold=True)

    # 9. User experience, privacy and limitations
    slide = new_slide(presentation)
    add_header(slide, "08  |  People and safety", "Designed to be approachable—and clear about limits",
               "The interface explains the simulation without suggesting that it controls real equipment.", 9)
    add_card(slide, 0.68, 1.7, 4.0, 4.65, fill=WHITE)
    add_picture_fit(slide, PHOTO, 0.82, 1.85, 3.72, 3.72)
    add_text(slide, "Real brooder photo • ELTORO.VET • CC0", 0.85, 5.8, 3.65, 0.24,
             size=9, color=MUTED, align=PP_ALIGN.CENTER)
    info_cards = [
        ("EASY START", "Quick setup for first runs; advanced controls can stay closed.", BLUE),
        ("ACCESSIBLE HELP", "Meet Pip keeps text available; speech plays only when requested.", TEAL),
        ("PERSISTENT THEME", "Light/dark choice is saved in the browser and reused on account pages.", ORANGE),
        ("ACCOUNT PRIVACY", "Hashed passwords, CSRF checks and per-user saved-run queries.", GREEN),
    ]
    for i, (title, body, accent) in enumerate(info_cards):
        col, row = i % 2, i // 2
        x, y = 4.98 + col * 3.92, 1.7 + row * 2.3
        add_card(slide, x, y, 3.62, 2.0, fill=WHITE)
        add_text(slide, title, x + 0.2, y + 0.22, 3.2, 0.22, size=10, color=accent, bold=True)
        add_text(slide, body, x + 0.2, y + 0.62, 3.2, 1.05, size=13, color=INK)
    add_card(slide, 4.98, 6.35, 7.54, 0.48, fill=PALE_ORANGE, line=PALE_ORANGE)
    add_text(slide, "Educational model only: simplified physics, no live sensors, no hardware control.",
             5.16, 6.48, 7.2, 0.2, size=10, color=ORANGE, bold=True)

    # 10. Demo and takeaways
    slide = new_slide(presentation)
    add_header(slide, "09  |  Presenting the project", "A short demo tells the whole story",
               "Show the user experience first, then connect it back to the model and experiments.", 10)
    add_card(slide, 0.68, 1.68, 6.05, 4.95, fill=WHITE)
    add_text(slide, "DEMO FLOW", 0.96, 1.98, 2.0, 0.25, size=10, color=BLUE, bold=True)
    demo_steps = [
        ("1", "Launch", "Run `py -3 -m webapp.app` or press F5 in VS Code."),
        ("2", "Set up", "Create an account and keep the recommended Quick setup values."),
        ("3", "Observe", "Run the simulation; watch temperature, heater power and the plots."),
        ("4", "Challenge it", "Try a cold night or rain, then compare a saved run."),
    ]
    for i, (number, title, body) in enumerate(demo_steps):
        y = 2.43 + i * 0.91
        add_text(slide, number, 0.98, y, 0.32, 0.3, size=17, color=BLUE, bold=True)
        add_text(slide, title, 1.4, y, 1.25, 0.24, size=13, color=INK, bold=True)
        add_text(slide, body, 2.7, y, 3.65, 0.55, size=11, color=MUTED)
    add_card(slide, 7.02, 1.68, 5.66, 4.95, fill=DARK_BG, line=DARK_BG)
    add_text(slide, "TAKEAWAYS", 7.32, 1.98, 2.0, 0.25, size=10,
             color=RGBColor(139, 191, 255), bold=True)
    takeaways = [
        "PI control removes steady-state error when heater capacity is sufficient.",
        "Capacity and insulation define the physical limit; tuning cannot defeat saturation.",
        "RK4 is much more reliable than coarse Euler steps for this stiff PID example.",
    ]
    for i, text in enumerate(takeaways):
        add_bullet(slide, text, 7.32, 2.52 + i * 1.02, 4.95, size=14,
                   color=WHITE, dot_color=RGBColor(139, 191, 255))
    add_text(slide, "Questions?", 7.32, 5.95, 2.1, 0.35, size=22, color=WHITE, bold=True)

    presentation.save(OUTPUT)
    print(f"Saved {OUTPUT}")


if __name__ == "__main__":
    build_deck()
