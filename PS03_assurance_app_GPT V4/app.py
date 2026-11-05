from __future__ import annotations
import sys
import html
import os
from pathlib import Path
from PySide6.QtCore import Qt, QRectF, QSize, Signal, QThread
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QFontDatabase
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QGridLayout, QStackedWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QComboBox, QLineEdit, QScrollArea, QProgressBar,
    QTabWidget, QSizePolicy, QMessageBox, QDialog, QFormLayout, QDialogButtonBox, QTextBrowser
)
import database as db
import ai_provider

BG = "#0b1017"
PANEL = "#111923"
PANEL2 = "#151f2b"
LINE = "#263443"
TEXT = "#edf3f8"
MUTED = "#98a9b8"
TEAL = "#54dfca"
AMBER = "#f2c76e"
RED = "#ff777f"
BLUE = "#80bfff"

STATUS_COLORS = {"Red": RED, "Amber": AMBER, "Green": TEAL, "Unknown": "#9aa7b3", "Pending": BLUE,
                 "Accepted": TEAL, "Rejected": "#778491", "Open": BLUE, "In progress": AMBER,
                 "Overdue": RED, "Completed": TEAL, "Verified": TEAL, "Blocked": RED,
                 "Critical": RED, "High": AMBER, "Medium": BLUE, "Low": MUTED}

UI_FONT = "Segoe UI"

APP_STYLE = f"""
QMainWindow, QWidget {{ background-color: {BG}; color: {TEXT}; font-family: '{UI_FONT}'; font-size: 10pt; }}
QFrame#Sidebar {{ background-color: #0e151e; border-right: 1px solid {LINE}; }}
QFrame#Panel {{ background-color: {PANEL}; border: 1px solid {LINE}; border-radius: 14px; }}
QFrame#KpiCard {{ background-color: {PANEL}; border: 1px solid {LINE}; border-radius: 14px; }}
QLabel {{ color: {TEXT}; }}
QLabel#Muted {{ color: {MUTED}; }}
QLabel#PageTitle {{ font-size: 23pt; font-weight: 700; color: #f5f8fb; }}
QLabel#SectionTitle {{ font-size: 12pt; font-weight: 700; color: #edf3f8; }}
QLabel#KpiValue {{ font-size: 24pt; font-weight: 700; color: #f5f8fb; }}
QLabel#KpiCaption {{ font-size: 9pt; color: {MUTED}; }}
QPushButton {{ background: #182432; color: {TEXT}; border: 1px solid #304153; border-radius: 8px; padding: 8px 12px; font-weight: 600; }}
QPushButton:hover {{ border-color: {TEAL}; background: #1b2b37; }}
QPushButton:checked {{ background: #183936; border-color: {TEAL}; color: #aaffef; }}
QPushButton#Primary {{ background: #174b48; border-color: #247b72; color: #dcfff7; }}
QPushButton#Danger {{ background: #38252b; border-color: #684047; color: #ffd8dc; }}
QPushButton#AcceptRecommendation {{ background: #087f5b; border: 2px solid #55d6a5; color: #ffffff; font-weight: 700; }}
QPushButton#AcceptRecommendation:hover {{ background: #099268; }}
QPushButton#RejectRecommendation {{ background: #b42318; border: 2px solid #ff8a80; color: #ffffff; font-weight: 700; }}
QPushButton#RejectRecommendation:hover {{ background: #d12d20; }}
QPushButton#EditRecommendation {{ background: #1d4ed8; border: 2px solid #8bb5ff; color: #ffffff; font-weight: 700; }}
QPushButton#EditRecommendation:hover {{ background: #2563eb; }}
QLineEdit, QComboBox {{ background: #0d151e; border: 1px solid #2b3a49; border-radius: 8px; padding: 8px 10px; color: {TEXT}; selection-background-color: #245e59; }}
QComboBox QAbstractItemView {{ background: #111923; border: 1px solid #334252; selection-background-color: #214d4a; color: {TEXT}; }}
QTableWidget {{ background: #0e151e; alternate-background-color: #121c27; border: 1px solid {LINE}; border-radius: 10px; gridline-color: #1d2935; selection-background-color: #1b4141; selection-color: #ffffff; }}
QHeaderView::section {{ background: #17222e; color: #9fb3c3; border: none; border-bottom: 1px solid #304050; padding: 9px 8px; font-weight: 700; }}
QTableWidget::item {{ padding: 7px 6px; border-bottom: 1px solid #1e2a35; }}
QTabWidget::pane {{ border: 1px solid {LINE}; border-radius: 10px; top: -1px; }}
QTabBar::tab {{ background: #131d28; color: {MUTED}; padding: 9px 16px; border: 1px solid {LINE}; border-bottom: none; border-top-left-radius: 8px; border-top-right-radius: 8px; }}
QTabBar::tab:selected {{ color: #d9fff8; background: #183936; }}
QProgressBar {{ background: #202d38; border: none; border-radius: 5px; height: 8px; text-align: center; }}
QProgressBar::chunk {{ background: {TEAL}; border-radius: 5px; }}
QScrollArea {{ border: none; }}
"""


def label(text, object_name=None, color=None, size=None, bold=False, wrap=False):
    w = QLabel(str(text))
    if object_name: w.setObjectName(object_name)
    if color or size or bold:
        bits=[]
        if color: bits.append(f"color:{color}")
        if size: bits.append(f"font-size:{size}pt")
        if bold: bits.append("font-weight:700")
        w.setStyleSheet(";".join(bits))
    w.setWordWrap(wrap)
    return w


def panel(title=None, subtitle=None):
    f=QFrame(); f.setObjectName("Panel")
    l=QVBoxLayout(f); l.setContentsMargins(16,14,16,15); l.setSpacing(10)
    if title: l.addWidget(label(title, "SectionTitle"))
    if subtitle: l.addWidget(label(subtitle, "Muted", wrap=True))
    return f,l


def status_badge(status):
    c=STATUS_COLORS.get(status, MUTED)
    w=QLabel(f"●  {status.upper()}")
    w.setAlignment(Qt.AlignmentFlag.AlignCenter)
    qc=QColor(c); bg=f"rgba({qc.red()},{qc.green()},{qc.blue()},0.12)"; border=f"rgba({qc.red()},{qc.green()},{qc.blue()},0.40)"
    w.setStyleSheet(f"color:{c}; background:{bg}; border:1px solid {border}; border-radius:10px; padding:4px 9px; font-size:8pt; font-weight:800")
    w.setFixedHeight(25)
    return w


def make_table(headers, rows, widths=None, row_height=38):
    t=QTableWidget(len(rows),len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setAlternatingRowColors(True)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setWordWrap(True)
    t.setTextElideMode(Qt.TextElideMode.ElideRight)
    t.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    t.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    t.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    t.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(row_height)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    if widths:
        for i,w in enumerate(widths): t.horizontalHeader().setSectionResizeMode(i,QHeaderView.ResizeMode.Interactive); t.setColumnWidth(i,w)
        t.horizontalHeader().setSectionResizeMode(len(widths)-1,QHeaderView.ResizeMode.Stretch)
    for r,row in enumerate(rows):
        for c,value in enumerate(row):
            item=QTableWidgetItem(str(value if value is not None else "—"))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if isinstance(value, tuple):
                item=QTableWidgetItem(value[0]); item.setForeground(QColor(value[1]))
            item.setToolTip(item.text())
            t.setItem(r,c,item)
    t.resizeRowsToContents()
    visible_rows=min(max(len(rows),6),14)
    t.setMinimumHeight(max(300,52+visible_rows*min(row_height,42)))
    t.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
    return t


class DonutChart(QWidget):
    def __init__(self, counts, parent=None):
        super().__init__(parent); self.counts=counts; self.setMinimumSize(220,205)
    def paintEvent(self, event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect=QRectF(15,12,175,175); total=sum(self.counts.values()) or 1
        colors={"Red":QColor(255,119,127),"Amber":QColor(242,199,110),"Green":QColor(84,223,202),"Unknown":QColor(154,167,179)}
        angle=90*16
        for key in ("Red","Amber","Green","Unknown"):
            n=self.counts.get(key,0)
            if n:
                span=round(360*16*n/total); p.setPen(Qt.PenStyle.NoPen); p.setBrush(colors[key]); p.drawPie(rect,angle,-span); angle-=span
        p.setBrush(QColor(PANEL)); p.drawEllipse(QRectF(52,49,101,101))
        p.setPen(QColor(TEXT)); p.setFont(QFont(UI_FONT,18,QFont.Weight.Bold)); p.drawText(QRectF(50,78,105,27),Qt.AlignmentFlag.AlignCenter,str(total))
        p.setPen(QColor(MUTED)); p.setFont(QFont(UI_FONT,8)); p.drawText(QRectF(50,104,105,22),Qt.AlignmentFlag.AlignCenter,"ENGAGEMENTS")
        p.end()


class MiniBarChart(QWidget):
    def __init__(self, items, parent=None):
        super().__init__(parent); self.items=items; self.setMinimumHeight(184)
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w=self.width(); left=145; right=w-42; plotw=max(120,right-left); rowh=27
        for i,(name,value,color) in enumerate(self.items):
            y=18+i*rowh
            p.setPen(QColor(MUTED)); p.setFont(QFont(UI_FONT,8)); p.drawText(0,y+12,138,18,Qt.AlignmentFlag.AlignRight,name)
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#202c38")); p.drawRoundedRect(QRectF(left,y+3,plotw,12),6,6)
            p.setBrush(QColor(color)); p.drawRoundedRect(QRectF(left,y+3,plotw*max(0,min(100,value))/100,12),6,6)
            p.setPen(QColor(TEXT)); p.drawText(int(right+7),y+13,f"{value:.0f}%")
        p.end()


class KpiCard(QFrame):
    def __init__(self,title,value,delta,accent=TEAL):
        super().__init__(); self.setObjectName("KpiCard")
        lay=QVBoxLayout(self); lay.setContentsMargins(16,13,16,14); lay.setSpacing(3)
        lay.addWidget(label(title,"KpiCaption")); lay.addWidget(label(value,"KpiValue"))
        lay.addWidget(label(delta,color=accent,size=8))


class PageHeader(QWidget):
    def __init__(self,title,subtitle,actions=None):
        super().__init__(); row=QHBoxLayout(self); row.setContentsMargins(0,0,0,0)
        col=QVBoxLayout(); col.setSpacing(3); col.addWidget(label(title,"PageTitle")); col.addWidget(label(subtitle,"Muted",wrap=True)); row.addLayout(col,1)
        if actions:
            for w in actions: row.addWidget(w,0,Qt.AlignmentFlag.AlignVCenter)


class DashboardPage(QWidget):
    def __init__(self, open_detail):
        super().__init__(); self.open_detail=open_detail; self.build()
    def build(self):
        outer=QVBoxLayout(self); outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
        content=QWidget(); root=QVBoxLayout(content); root.setContentsMargins(26,22,26,24); root.setSpacing(17)
        root.addWidget(PageHeader("Executive portfolio", "An evidence-led view of software quality, service stability, and delivery assurance."))
        summary=db.portfolio_summary(); counts=summary["statuses"]
        cards=QHBoxLayout(); cards.setSpacing(12)
        cards.addWidget(KpiCard("ENGAGEMENTS", "28", "5 business units", BLUE))
        cards.addWidget(KpiCard("RED PRIORITY", str(counts.get("Red",0)), "Verified critical risks", RED))
        cards.addWidget(KpiCard("RELEASE TRACEABILITY", f"{summary['traceable']}/{summary['releases']}", "64% of the release sample", AMBER))
        cards.addWidget(KpiCard("ACTIONS OVERDUE", f"{summary['overdue']}/{summary['actions']}", "31% of baseline actions", AMBER))
        root.addLayout(cards)
        top=QHBoxLayout(); top.setSpacing(14)
        health,panel_l=panel("Portfolio health", "Case starting mix. Statuses are explained by engagement-level evidence."); health.setMinimumHeight(260)
        inner=QHBoxLayout(); inner.addWidget(DonutChart(counts),0)
        legend=QVBoxLayout(); legend.setSpacing(10)
        for s in ("Red","Amber","Green","Unknown"):
            n=counts.get(s,0); row=QHBoxLayout(); row.addWidget(status_badge(s)); row.addStretch(1); row.addWidget(label(str(n),color=STATUS_COLORS[s],bold=True)); legend.addLayout(row)
        legend.addStretch(1); legend.addWidget(label("As of 05 Nov 2026 · portfolio data current through 05 Nov 2026", "Muted", wrap=True)); inner.addLayout(legend,1); panel_l.addLayout(inner)
        signals,sl=panel("Assurance signals", "Selected portfolio metrics from the supplied exercise inputs."); signals.setMinimumHeight(260)
        metrics=[("Commitments met",db.average_observation("Commitments met"),TEAL),("SLO compliance",db.average_observation("SLO compliance"),TEAL),("Traceable releases",64,AMBER),("Repeat findings",22,AMBER),("Overdue actions",31,RED)]
        sl.addWidget(MiniBarChart(metrics)); sl.addWidget(label("Green target is >95% for positive percentage measures. Other bands are demo assumptions.","Muted",wrap=True))
        top.addWidget(health,1); top.addWidget(signals,1); root.addLayout(top)
        bottom=QHBoxLayout(); bottom.setSpacing(14)
        risks,rl=panel("Priority engagements", "Select a row to review the evidence and rating rationale.")
        engs=db.get_engagements()
        rows=[]
        for e in engs[:8]: rows.append([e["engagement_id"],e["name"],e["business_unit"],(e["overall_status"],STATUS_COLORS.get(e["overall_status"],MUTED)),e["evidence_confidence"]])
        self.table=make_table(["ID","ENGAGEMENT","BUSINESS UNIT","HEALTH","EVIDENCE"],rows,[82,165,130,66,76],34)
        risks.setMinimumHeight(360); self.table.cellClicked.connect(self.row_clicked); rl.addWidget(self.table); bottom.addWidget(risks,2)
        plan,pl=panel("30 / 60 / 90 day plan", "Contain risk → strengthen controls → verify sustained outcomes.")
        hcounts=db.action_counts_by_horizon()
        for day,caption,count in [(30,"Stabilize & contain",hcounts.get(30,0)),(60,"Correct & control",hcounts.get(60,0)),(90,"Verify & improve",hcounts.get(90,0))]:
            r=QHBoxLayout(); r.addWidget(label(f"DAY {day}",color=TEAL,bold=True)); r.addWidget(label(caption)); r.addStretch(1); r.addWidget(label(str(count),color=TEXT,bold=True)); pl.addLayout(r)
        pl.addWidget(label("Every accepted action has one accountable owner, a due date, an outcome, and closure evidence.","Muted",wrap=True)); plan.setMinimumHeight(360); bottom.addWidget(plan,1)
        root.addLayout(bottom,1)
        scroll.setWidget(content); outer.addWidget(scroll)
    def row_clicked(self,row,col):
        item=self.table.item(row,0)
        if item: self.open_detail(item.text())


class EngagementsPage(QWidget):
    def __init__(self, open_detail):
        super().__init__(); self.open_detail=open_detail
        root=QVBoxLayout(self); root.setContentsMargins(26,22,26,24); root.setSpacing(15)
        root.addWidget(PageHeader("Engagements", "Filter the portfolio and open an engagement to inspect its health dimensions and evidence."))
        filters=QHBoxLayout(); self.search=QLineEdit(); self.search.setPlaceholderText("Search ID, engagement name, or unit")
        self.status=QComboBox(); self.status.addItems(["All","Red","Amber","Green","Unknown"])
        self.unit=QComboBox(); self.unit.addItems(["All"]+db.UNITS)
        self.search.textChanged.connect(self.refresh); self.status.currentTextChanged.connect(self.refresh); self.unit.currentTextChanged.connect(self.refresh)
        filters.addWidget(self.search,2); filters.addWidget(self.status); filters.addWidget(self.unit); root.addLayout(filters)
        p,pl=panel("Portfolio register", "Overall status is derived from the seeded demonstration evidence and proposed rules.")
        self.table=make_table(["ID","ENGAGEMENT","UNIT","TYPE","HEALTH","EVIDENCE CONFIDENCE","AS OF"],[],[95,210,130,150,90,140,110],42)
        self.table.cellClicked.connect(self.row_clicked); pl.addWidget(self.table); root.addWidget(p,1); self.refresh()
    def refresh(self,*args):
        rows=db.get_engagements(self.search.text(),self.status.currentText(),self.unit.currentText())
        self.table.setRowCount(len(rows))
        for i,e in enumerate(rows):
            vals=[e["engagement_id"],e["name"],e["business_unit"],e["engagement_type"],(e["overall_status"],STATUS_COLORS.get(e["overall_status"],MUTED)),e["evidence_confidence"],e["as_of"]]
            for j,v in enumerate(vals): self.table.setItem(i,j,QTableWidgetItem(v[0] if isinstance(v,tuple) else str(v)))
            self.table.item(i,4).setForeground(QColor(STATUS_COLORS.get(e["overall_status"],MUTED)))
    def row_clicked(self,row,col):
        item=self.table.item(row,0)
        if item: self.open_detail(item.text())


class DetailPage(QWidget):
    def __init__(self,eid,back):
        super().__init__(); self.eid=eid; self.back=back; self.build()
    def build(self):
        e=db.get_engagement(self.eid)
        root=QVBoxLayout(self); root.setContentsMargins(26,22,26,24); root.setSpacing(15)
        back=QPushButton("←  Back to engagements"); back.clicked.connect(self.back); back.setFixedWidth(190)
        head=PageHeader(f"{e['engagement_id']}  ·  {e['name']}", f"{e['business_unit']}  /  {e['engagement_type']}  /  As of {e['as_of']}",[status_badge(e["overall_status"])])
        root.addWidget(back); root.addWidget(head)
        note,pnl=panel("Rating rationale", e["health_reason"]); r=QHBoxLayout(); r.addWidget(status_badge(e["overall_status"])); r.addWidget(label(f"Evidence confidence: {e['evidence_confidence']}",color=AMBER if e['evidence_confidence']=="Medium" else TEAL,bold=True)); r.addStretch(1); pnl.addLayout(r); root.addWidget(note)
        obs=db.get_observations(self.eid)
        p,pl=panel("Health dimensions", "Metric values, statuses, confidence, and rationale. Thresholds are proposed demo assumptions.")
        rows=[]
        for o in obs:
            value=(f"${o['value']:,.0f}" if o['unit']=="USD" else f"{o['value']:.1f}{o['unit']}") if o["value"] is not None else "Unknown"
            rows.append([o["dimension"],o["metric"],value,(o["status"],STATUS_COLORS.get(o["status"],MUTED)),o["confidence"],o["explanation"]])
        tbl=make_table(["DIMENSION","MEASURE","VALUE","STATUS","EVIDENCE","RATING / CONTEXT"],rows,[140,190,95,90,95,360],48); pl.addWidget(tbl); root.addWidget(p,1)
        actions=db.get_actions()
        selected=[a for a in actions if a["engagement_id"]==self.eid][:4]
        if selected:
            p2,l2=panel("Linked actions", "Each action has one accountable owner.")
            for a in selected:
                row=QHBoxLayout(); row.addWidget(label(f"{a['action_id']} · {a['title']}",bold=True,wrap=True),2); row.addWidget(label(f"{a['owner']}  ·  Day {a['horizon']}",color=TEAL,wrap=True),1); row.addWidget(status_badge(a["status"])); l2.addLayout(row)
            root.addWidget(p2)


class RecommendationCard(QFrame):
    def __init__(self,rec,refresh):
        super().__init__(); self.setObjectName("Panel")
        l=QVBoxLayout(self); l.setContentsMargins(17,15,17,15); l.setSpacing(9)
        top=QHBoxLayout(); top.addWidget(label(f"{rec['recommendation_id']}  ·  {rec['engagement_name']}",color=TEAL,bold=True))
        if rec["recommendation_id"].startswith("REC-AI-"):
            top.addWidget(label("AI Recommendation",color="#c4a7ff",size=8,bold=True))
        top.addStretch(1); top.addWidget(status_badge(rec["priority"])); l.addLayout(top)
        actions=QHBoxLayout(); actions.setSpacing(10)
        if rec["status"]=="Pending":
            actions.addWidget(label("REVIEW ACTIONS",color=MUTED,size=8,bold=True))
            actions.addStretch(1)
            accept=QPushButton("Accept"); accept.setObjectName("AcceptRecommendation"); accept.setMinimumSize(104,42); accept.setCursor(Qt.CursorShape.PointingHandCursor); accept.clicked.connect(lambda: self.approve(rec["recommendation_id"],refresh))
            reject=QPushButton("Reject"); reject.setObjectName("RejectRecommendation"); reject.setMinimumSize(104,42); reject.setCursor(Qt.CursorShape.PointingHandCursor); reject.clicked.connect(lambda: self.reject(rec["recommendation_id"],refresh))
            edit=QPushButton("Edit"); edit.setObjectName("EditRecommendation"); edit.setMinimumSize(104,42); edit.setCursor(Qt.CursorShape.PointingHandCursor); edit.clicked.connect(lambda: self.edit(rec,refresh))
            actions.addWidget(accept); actions.addWidget(reject); actions.addWidget(edit)
        else:
            actions.addWidget(label("REVIEW STATUS",color=MUTED,size=8,bold=True))
            actions.addStretch(1)
            actions.addWidget(status_badge(rec["status"]))
        l.addLayout(actions)
        l.addWidget(label(rec["title"],size=12,bold=True,wrap=True)); l.addWidget(label(rec["rationale"],"Muted",wrap=True))
        if "persona" in rec.keys() and rec["persona"]:
            l.addWidget(label(f"Prepared for: {rec['persona']}",color=TEAL,wrap=True))
        facts=QHBoxLayout(); facts.addWidget(label(f"Owner role: {rec['owner']}",color=BLUE,wrap=True)); facts.addWidget(label(f"Horizon: Day {rec['horizon']}",color=TEAL,wrap=True)); facts.addWidget(label(f"Confidence: {rec['confidence']}",color=AMBER,wrap=True)); facts.addStretch(1); l.addLayout(facts)
        l.addWidget(label(f"Evidence reference: {rec['trigger_ref']}  ·  Human review required",color=MUTED,size=8,wrap=True))
        if rec["assumptions"]: l.addWidget(label(f"Assumptions / uncertainty: {rec['assumptions']}",color=AMBER,size=8,wrap=True))
    def edit(self,rec,refresh):
        dialog=QDialog(self); dialog.setWindowTitle("Edit Action recommendation"); dialog.setMinimumWidth(520)
        form=QFormLayout(dialog)
        title=QLineEdit(rec["title"]); owner=QLineEdit(rec["owner"])
        horizon=QComboBox()
        for days in (30,60,90): horizon.addItem(f"Day {days}",days)
        idx=horizon.findData(rec["horizon"]); horizon.setCurrentIndex(max(0,idx))
        priority=QComboBox(); priority.addItems(["Critical","High","Medium","Low"]); priority.setCurrentText(rec["priority"])
        outcome=QLineEdit(rec["outcome"]); measure=QLineEdit(rec["success_measure"])
        form.addRow("Action",title); form.addRow("Accountable owner",owner); form.addRow("Horizon",horizon)
        form.addRow("Priority",priority); form.addRow("Expected outcome",outcome); form.addRow("Success measure",measure)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); form.addRow(buttons)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            if not owner.text().strip() or not title.text().strip():
                QMessageBox.warning(self,"Required fields","Action title and one accountable owner are required."); return
            db.update_recommendation(rec["recommendation_id"],title.text().strip(),owner.text().strip(),horizon.currentData(),outcome.text().strip(),measure.text().strip(),priority.currentText())
            refresh()
    def approve(self,rid,refresh):
        if db.approve_recommendation(rid): refresh()
    def reject(self,rid,refresh):
        db.dismiss_recommendation(rid); refresh()


RECOMMENDATION_PERSONAS = {
    "Executive sponsor": "Focus on portfolio exposure, customer and business outcomes, cross-engagement dependencies, and decisions or escalations requiring leadership attention.",
    "Delivery assurance lead": "Focus on control effectiveness, evidence quality, measurable risk reduction, accountable owners, and assurance follow-up.",
    "Account lead": "Focus on customer impact, contractual commitments, transparent communications, recovery confidence, and relationship risk.",
    "Engineering manager": "Focus on release quality, defect containment, root-cause learning, test effectiveness, and engineering capacity.",
    "Service manager": "Focus on SLO performance, incidents, service continuity, operational capacity, and recovery actions.",
    "Risk and compliance officer": "Focus on control gaps, obligations, auditable evidence, exposure containment, and verification.",
    "Commercial and finance lead": "Focus on validated penalty exposure, financial impact, forecast changes, cost of remediation, and confirmation of assumptions.",
}


class RecommendationWorker(QThread):
    generated = Signal(str, dict)
    failed = Signal(str)
    def __init__(self, engagement_id, persona_name):
        super().__init__(); self.engagement_id=engagement_id; self.persona_name=persona_name
    def run(self):
        try:
            context=db.get_ai_context(self.engagement_id)
            result=ai_provider.generate_recommendation(context,self.persona_name,RECOMMENDATION_PERSONAS[self.persona_name])
            self.generated.emit(self.engagement_id,result)
        except Exception as exc:
            self.failed.emit(str(exc))


class RecommendationsPage(QWidget):
    def __init__(self): super().__init__(); self.worker=None; self.build()
    def build(self):
        root=QVBoxLayout(self); root.setContentsMargins(26,22,26,24); root.setSpacing(14)
        root.addWidget(PageHeader("Recommendation review", "Review proposed actions against evidence, ownership, priority, and timing."))
        live_row=QHBoxLayout(); self.persona_picker=QComboBox()
        for persona in RECOMMENDATION_PERSONAS: self.persona_picker.addItem(persona)
        self.engagement_picker=QComboBox()
        for e in db.get_engagements(): self.engagement_picker.addItem(f"{e['engagement_id']} · {e['name']}",e['engagement_id'])
        self.generate_button=QPushButton("Generate AI Recommendation"); self.generate_button.setObjectName("Primary")
        self.generate_button.setEnabled(ai_provider.provider_ready()); self.generate_button.clicked.connect(self.generate_live)
        self.live_status=label("Select a persona to tailor the recommendation perspective.","Muted",wrap=True)
        live_row.addWidget(label("Persona")); live_row.addWidget(self.persona_picker,2); live_row.addWidget(label("Engagement")); live_row.addWidget(self.engagement_picker,3); live_row.addWidget(self.generate_button); root.addLayout(live_row)
        root.addWidget(self.live_status)
        banner,p=panel("Human approval is required", "Metric calculations and health statuses come from configured rules. A reviewer must accept, edit, or reject every recommendation before an action is assigned.")
        p.addWidget(label("Facts and hypotheses must be distinguished; insufficient evidence should trigger a request for evidence rather than an invented cause.","Muted",wrap=True)); root.addWidget(banner)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); content=QWidget(); v=QVBoxLayout(content); v.setSpacing(11)
        recs=db.get_recommendations("All")
        for rec in recs: v.addWidget(RecommendationCard(rec,self.reload))
        v.addStretch(1); scroll.setWidget(content); root.addWidget(scroll,1)
        self.root_layout=root; self.scroll=scroll
    def reload(self):
        content=QWidget(); v=QVBoxLayout(content); v.setSpacing(11)
        for rec in db.get_recommendations("All"): v.addWidget(RecommendationCard(rec,self.reload))
        v.addStretch(1); self.scroll.setWidget(content)
    def generate_live(self):
        if not ai_provider.provider_ready(): return
        eid=self.engagement_picker.currentData()
        self.generate_button.setEnabled(False); self.live_status.setText("Preparing a recommendation for the selected persona…")
        self.worker=RecommendationWorker(eid,self.persona_picker.currentText())
        self.worker.generated.connect(self.on_generated); self.worker.failed.connect(self.on_failed)
        self.worker.finished.connect(lambda:self.generate_button.setEnabled(ai_provider.provider_ready()))
        self.worker.start()
    def on_generated(self,eid,result):
        try:
            result["persona"]=self.persona_picker.currentText()
            db.save_ai_recommendation(eid,result)
            self.live_status.setText(f"Live draft created for {eid}. Review evidence references before approval.")
            self.reload()
        except Exception as exc: self.on_failed(str(exc))
    def on_failed(self,message): self.live_status.setText(f"Recommendation generation failed: {message}")


class ChatWorker(QThread):
    answered=Signal(str,str)
    failed=Signal(str)
    def __init__(self,question): super().__init__(); self.question=question
    def run(self):
        try:
            answer,model=ai_provider.generate_chat_answer(self.question,db.get_chat_context(self.question))
            self.answered.emit(answer,model)
        except Exception as exc: self.failed.emit(str(exc))


class ChatPage(QWidget):
    def __init__(self):
        super().__init__(); self.history=[]; self.worker=None; self.pending_question=""; self.build()
    def build(self):
        root=QVBoxLayout(self); root.setContentsMargins(26,22,26,24); root.setSpacing(14)
        source="Responses are grounded in available case evidence."
        root.addWidget(PageHeader("Assurance Chatbot", "Ask about portfolio health, evidence, SLO breaches, recommendations, or the 30/60/90-day plan.", [label("POLITE · NEUTRAL",color=TEAL,size=8,bold=True)]))
        row=QHBoxLayout(); row.setSpacing(14)
        chat_panel,chat_layout=panel("Ask a question", source)
        self.transcript=QTextBrowser(); self.transcript.setMinimumHeight(455); self.transcript.setOpenExternalLinks(False)
        self.transcript.setStyleSheet("QTextBrowser { background:#0d151e; border:1px solid #263443; border-radius:10px; padding:12px; color:#edf3f8; }")
        self.history.append(("assistant","Hello. I can help interpret the assurance portfolio and explain the evidence behind an engagement status."))
        self.refresh_transcript(); chat_layout.addWidget(self.transcript,1)
        input_row=QHBoxLayout(); self.question=QLineEdit(); self.question.setPlaceholderText("Ask a delivery assurance question…")
        self.question.returnPressed.connect(self.send_question)
        self.send_button=QPushButton("Send"); self.send_button.setObjectName("Primary"); self.send_button.clicked.connect(self.send_question)
        input_row.addWidget(self.question,1); input_row.addWidget(self.send_button); chat_layout.addLayout(input_row)
        self.chat_status=label("Responses use case evidence and do not change ratings or assign actions.","Muted",wrap=True); chat_layout.addWidget(self.chat_status)
        row.addWidget(chat_panel,3)
        quick,ql=panel("Try asking", "Suggested questions")
        examples=["Why is ENG-007 Red?","What is the evidence gap for SRV-012?","How many actions are overdue?","How are SLO breaches and penalties treated?","Summarize the portfolio health mix."]
        for text in examples:
            b=QPushButton(text); b.setMinimumHeight(38); b.clicked.connect(lambda checked=False,q=text:self.ask_example(q)); ql.addWidget(b)
        ql.addStretch(1)
        ql.addWidget(label("Answer policy",color=TEAL,bold=True))
        ql.addWidget(label("The assistant uses available case evidence, states when information is missing, and keeps verified facts separate from assumptions.","Muted",wrap=True))
        row.addWidget(quick,1); root.addLayout(row,1)
    def refresh_transcript(self):
        parts=["<html><body style='font-family:Segoe UI,Arial,sans-serif;color:#edf3f8;font-size:10pt;'>"]
        for role,text in self.history:
            assistant=(role=="assistant")
            color="#54dfca" if assistant else "#80bfff"
            name="ASSURANCE ASSISTANT" if assistant else "YOU"
            safe=html.escape(str(text)).replace("\n","<br>")
            parts.append(f"<p style='margin:7px 0 3px;color:{color};font-weight:bold'>{name}</p><p style='margin:0 0 13px;line-height:1.45'>{safe}</p>")
        parts.append("</body></html>")
        self.transcript.setHtml("".join(parts)); self.transcript.verticalScrollBar().setValue(self.transcript.verticalScrollBar().maximum())
    def ask_example(self,question): self.question.setText(question); self.send_question()
    def send_question(self):
        question=self.question.text().strip()
        if not question:return
        self.history.append(("user",question)); self.refresh_transcript(); self.question.clear()
        if ai_provider.provider_ready():
            self.send_button.setEnabled(False); self.chat_status.setText("Preparing an evidence-grounded response from case evidence…")
            self.pending_question=question; self.worker=ChatWorker(question)
            self.worker.answered.connect(self.on_answer); self.worker.failed.connect(self.on_error)
            self.worker.finished.connect(lambda:self.send_button.setEnabled(True)); self.worker.start()
        else:
            answer=self.offline_answer(question)
            self.history.append(("assistant",answer)); self.refresh_transcript()
        self.chat_status.setText("Response prepared.")
    def on_answer(self,answer,model):
        self.history.append(("assistant",answer)); self.refresh_transcript()
        self.chat_status.setText("Response prepared from the available case evidence. Please review before making decisions.")
    def on_error(self,message):
        answer=self.offline_answer(self.pending_question)
        self.history.append(("assistant",answer+"\n\nA response could not be completed. Please try again."))
        self.refresh_transcript(); self.chat_status.setText("The answer uses available local case evidence. Please verify important decisions.")
    def offline_answer(self,question):
        q=question.lower(); summary=db.portfolio_summary()
        if "eng-007" in q:
            e=db.get_engagement("ENG-007")
            obs=db.get_observations("ENG-007")
            measures="; ".join(f"{o['metric']}: {o['value']}{o['unit']} ({o['status']})" for o in obs if o["metric"] in ("Commitments met","Failed / rolled-back releases","SLO compliance"))
            return f"ENG-007 is {e['overall_status']}. Its milestones are {measures.split(';')[0]}, while release quality is Red based on verified defect leakage and the failed-release rate. The rating is driven by release risk, not by milestone status. Evidence: F-001 and REL-012. "
        if "srv-012" in q:
            e=db.get_engagement("SRV-012")
            return f"SRV-012 is {e['overall_status']}. Service stability is Green at 99% SLO compliance, while sampled release traceability is 64% and Amber. The overall Amber status reflects the verified evidence-control gap; incomplete evidence does not by itself mean poor service performance. "
        if "slo" in q or "penalt" in q:
            e=db.get_engagement("ENG-021")
            return f"The demo treats a critical or repeated SLO breach, or an assessed material penalty, as a Red service-stability trigger. ENG-021 is {e['overall_status']} in the case data, with an 89% SLO compliance measure and $18,000 penalty exposure. These are illustrative records, not real contract results."
        if "action" in q or "overdue" in q or "30" in q or "60" in q or "90" in q:
            horizons=db.action_counts_by_horizon()
            return f"The portfolio has {summary['overdue']} overdue actions out of {summary['actions']} (31% when rounded). Actions are grouped by horizon: Day 30: {horizons.get(30,0)}, Day 60: {horizons.get(60,0)}, Day 90: {horizons.get(90,0)}. Each action has one accountable owner."
        if "trace" in q or "evidence" in q:
            return f"The release sample has {summary['traceable']} fully traceable releases out of {summary['releases']} (64%). SRV-012 is an illustrative service engagement with 64% traceability and stable 99% SLO compliance. Missing evidence is an evidence gap, not automatic proof of poor service performance."
        if "repeat" in q or "finding" in q:
            return f"The portfolio has {summary['repeats']} repeated findings out of {summary['findings']} findings (22%). Review repeat findings for verified recurrence and assign a single accountable owner to corrective actions."
        if "portfolio" in q or "health" in q or "overall" in q:
            counts=summary["statuses"]
            return f"The portfolio contains 28 engagements across five business units: {counts.get('Red',0)} Red, {counts.get('Amber',0)} Amber, and {counts.get('Green',0)} Green. The supplied case signals include 11 repeat findings from 50, 9 overdue actions from 29, and 16 traceable releases from 25."
        return "I can answer questions about engagement health, release quality, evidence traceability, SLO breaches and penalties, findings, and the 30/60/90-day action plan. Try naming ENG-007 or SRV-012, or ask for the portfolio health mix."


class PlanPage(QWidget):
    def __init__(self): super().__init__(); self.build()
    def build(self):
        root=QVBoxLayout(self); root.setContentsMargins(26,22,26,24); root.setSpacing(15)
        root.addWidget(PageHeader("30 / 60 / 90 day plan", "Stabilize and contain → correct and control → verify sustained outcomes."))
        summary=QHBoxLayout(); summary.setSpacing(12)
        for day,title,subtitle in [(30,"Stabilize & contain","Immediate customer, release, service, or audit exposure"),(60,"Correct & control","Root cause, preventive controls, and priority evidence"),(90,"Verify & improve","Effectiveness check, recurrence review, scale decision")]:
            f,l=panel(f"DAY {day}",title); l.addWidget(label(subtitle,"Muted",wrap=True)); summary.addWidget(f)
        root.addLayout(summary)
        tabs=QTabWidget()
        for day in (30,60,90):
            widget=QWidget(); vl=QVBoxLayout(widget); actions=db.get_actions(day)
            rows=[]
            for a in actions: rows.append([a["action_id"],a["engagement_id"],a["title"],a["owner"],a["due_date"],(a["status"],STATUS_COLORS.get(a["status"],MUTED)),a["success_measure"]])
            table=make_table(["ACTION ID","ENG ID","ACTION","OWNER","DUE DATE","STATUS","SUCCESS MEASURE"],rows,[90,85,180,140,95,80,160],44)
            table.cellDoubleClicked.connect(lambda r,c, t=table: self.edit_action(t,r))
            vl.addWidget(label("Double-click a row to update its tracking status.","Muted")); vl.addWidget(table)
            tabs.addTab(widget,f"Day {day} · {len(actions)} actions")
        root.addWidget(tabs,1)
        root.addWidget(label("Completion is owner-reported; effectiveness becomes verified only after a reviewer checks the evidence.","Muted",wrap=True))
    def edit_action(self,table,row):
        item=table.item(row,0)
        if not item:return
        action_id=item.text()
        dlg=QMessageBox(self); dlg.setWindowTitle("Update action")
        dlg.setText(f"Choose a new status for {action_id}.")
        opts={"Open":dlg.addButton("Open",QMessageBox.ButtonRole.ActionRole),
              "In progress":dlg.addButton("In progress",QMessageBox.ButtonRole.ActionRole),
              "Overdue":dlg.addButton("Overdue",QMessageBox.ButtonRole.ActionRole),
              "Blocked":dlg.addButton("Blocked",QMessageBox.ButtonRole.ActionRole),
              "Completed":dlg.addButton("Completed",QMessageBox.ButtonRole.ActionRole),
              "Verified":dlg.addButton("Verified",QMessageBox.ButtonRole.ActionRole)}
        dlg.addButton("Cancel",QMessageBox.ButtonRole.RejectRole); dlg.exec()
        for status,button in opts.items():
            if dlg.clickedButton()==button:
                db.update_action_status(action_id,status)
                table.item(row,5).setText(status)
                table.item(row,5).setForeground(QColor(STATUS_COLORS.get(status,MUTED)))
                return



class EvidencePage(QWidget):
    def __init__(self): super().__init__(); self.build()
    def build(self):
        root=QVBoxLayout(self); root.setContentsMargins(26,22,26,24); root.setSpacing(14)
        root.addWidget(PageHeader("Evidence & findings", "Inspect the release sample and quality/service findings supporting portfolio signals."))
        s=db.portfolio_summary()
        p,l=panel("Sample integrity", f"{s['traceable']} of {s['releases']} sampled releases fully traceable (64%) · {s['repeats']} of {s['findings']} findings marked repeat (22%). ")
        l.addWidget(label("Missing evidence is displayed as an evidence gap. It does not, by itself, establish poor service or delivery performance.","Muted",wrap=True)); root.addWidget(p)
        tabs=QTabWidget()
        release_rows=[]
        for r in db.get_releases():
            trace="Traceable" if r["fully_traceable"] else "Gap"
            failed="Yes" if r["failed"] else "No"
            release_rows.append([r["release_id"],r["engagement_id"],r["engagement_name"],r["release_date"],failed,(trace,TEAL if trace=="Traceable" else AMBER),f"A:{r['approval_evidence']} · T:{r['test_evidence']} · C:{r['change_evidence']}",r["evidence_ref"]])
        rt=make_table(["REL ID","ENG ID","ENGAGEMENT","DATE","FAILED","TRACE","EVIDENCE A/T/C","EVIDENCE REF"],release_rows,[72,75,150,86,65,78,120,145],42)
        for col,tip in enumerate(["Release identifier","Engagement identifier","Engagement name","Release date","Whether the release failed","Required evidence traceability","Approval / testing / change evidence present (1) or missing (0)","Evidence reference"]): rt.horizontalHeaderItem(col).setToolTip(tip)
        findings=[]
        for f in db.get_findings(50): findings.append([f["finding_id"],f["engagement_id"],f["engagement_name"],f["category"],(f["severity"],STATUS_COLORS.get(f["severity"],MUTED)),"Yes" if f["repeat_flag"] else "No",f["customer_impact"],f["finding_date"],f["summary"]])
        ft=make_table(["FINDING","ENG ID","ENGAGEMENT","CATEGORY","SEVERITY","REPEAT","IMPACT","DATE","SUMMARY"],findings,[75,75,145,115,80,65,75,85,180],42)
        for col,tip in enumerate(["Finding ID","Engagement identifier","Engagement name","Finding category","Finding severity","Whether this finding repeats","Customer impact classification","Finding date","Finding summary"]): ft.horizontalHeaderItem(col).setToolTip(tip)
        rp=QWidget(); rl=QVBoxLayout(rp); rl.addWidget(rt)
        fp=QWidget(); fl=QVBoxLayout(fp); fl.addWidget(ft)
        tabs.addTab(rp,"Release samples · 25"); tabs.addTab(fp,"Findings · 50")
        root.addWidget(tabs,1)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("Delivery Assurance Executive App"); self.resize(1500,960); self.setMinimumSize(1180,760)
        shell=QWidget(); layout=QHBoxLayout(shell); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
        sidebar=QFrame(); sidebar.setObjectName("Sidebar"); sidebar.setFixedWidth(230); sl=QVBoxLayout(sidebar); sl.setContentsMargins(17,22,17,18); sl.setSpacing(7)
        sl.addWidget(label("ASSURANCE",color=TEAL,size=9,bold=True)); sl.addWidget(label("Delivery\nIntelligence",size=18,bold=True)); sl.addSpacing(13)
        sl.addWidget(label("WORKSPACE",color=MUTED,size=8,bold=True))
        self.stack=QStackedWidget(); self.pages={}; self.nav_buttons={}
        nav_items=[("dashboard","Executive Portfolio"),("engagements","Engagements"),("recommendations","Recommendations"),("chat","Assurance chatbot"),("plan","30 / 60 / 90 plan"),("evidence","Evidence and findings")]
        for key,title in nav_items:
            b=QPushButton(title); b.setCheckable(True); b.setCursor(Qt.CursorShape.PointingHandCursor); b.clicked.connect(lambda checked=False,k=key:self.navigate(k)); b.setMinimumHeight(39); sl.addWidget(b); self.nav_buttons[key]=b
        sl.addStretch(1)
        info,p=panel("CASE CONTEXT", "Delivery assurance portfolio\nAs of 05 Nov 2026")
        info.setStyleSheet("QFrame#Panel { background:#131c26; border:1px solid #304153; border-radius:12px; }")
        for i in range(p.count()):
            w=p.itemAt(i).widget()
            if isinstance(w,QLabel): w.setStyleSheet(f"color:{MUTED}; font-size:8pt")
        sl.addWidget(info)
        layout.addWidget(sidebar)
        content=QWidget(); cl=QVBoxLayout(content); cl.setContentsMargins(0,0,0,0); cl.setSpacing(0)
        top=QFrame(); top.setFixedHeight(54); top.setStyleSheet("background:#0e151e;border-bottom:1px solid #263443;")
        tl=QHBoxLayout(top); tl.setContentsMargins(22,0,22,0); tl.addWidget(label("DELIVERY ASSURANCE",color=MUTED,size=20,bold=True)); tl.addStretch(1); tl.addWidget(label("CASE REVIEW  ·  05 NOV 2026",color=TEAL,size=8,bold=True)); cl.addWidget(top)
        self.stack.setObjectName("MainStack"); cl.addWidget(self.stack,1); layout.addWidget(content,1)
        self.setCentralWidget(shell)
        db.init_db(); self.build_pages(); self.navigate("dashboard")
    def build_pages(self):
        self.pages={
          "dashboard":DashboardPage(self.open_detail),
          "engagements":EngagementsPage(self.open_detail),
          "recommendations":RecommendationsPage(),
          "chat":ChatPage(),
          "plan":PlanPage(),
          "evidence":EvidencePage(),
        }
        while self.stack.count():
            old=self.stack.widget(0)
            self.stack.removeWidget(old)
            old.deleteLater()
        for key in ("dashboard","engagements","recommendations","chat","plan","evidence"):
            self.stack.addWidget(self.pages[key])
    def navigate(self,key):
        if key not in self.pages:return
        self.stack.setCurrentWidget(self.pages[key])
        for k,b in self.nav_buttons.items(): b.setChecked(k==key)
    def open_detail(self,eid):
        page=DetailPage(eid,lambda:self.navigate("engagements"))
        self.stack.addWidget(page); self.stack.setCurrentWidget(page)
        for b in self.nav_buttons.values(): b.setChecked(False)


def main():
    db.init_db()
    app=QApplication(sys.argv); app.setStyle("Fusion")
    global UI_FONT
    fonts_dir=Path(os.getenv("WINDIR",r"C:\Windows"))/"Fonts"
    for candidate in (fonts_dir/"segoeui.ttf",fonts_dir/"arial.ttf"):
        if candidate.is_file():
            font_id=QFontDatabase.addApplicationFont(str(candidate))
            if font_id>=0:
                families=QFontDatabase.applicationFontFamilies(font_id)
                if families: UI_FONT=families[0]; break
    app.setFont(QFont(UI_FONT,10)); app.setStyleSheet(APP_STYLE.replace("Segoe UI",UI_FONT))
    win=MainWindow(); win.show(); sys.exit(app.exec())

if __name__=="__main__": main()


