from __future__ import annotations
import sys
from PySide6.QtCore import Qt, QRectF, QSize, Signal, QThread
from PySide6.QtGui import QColor, QPainter, QPen, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QGridLayout, QStackedWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QComboBox, QLineEdit, QScrollArea, QProgressBar,
    QTabWidget, QSizePolicy, QMessageBox, QDialog, QFormLayout, QDialogButtonBox
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

APP_STYLE = f"""
QMainWindow, QWidget {{ background-color: {BG}; color: {TEXT}; font-family: 'Segoe UI'; font-size: 10pt; }}
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
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(row_height)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    if widths:
        for i,w in enumerate(widths): t.horizontalHeader().setSectionResizeMode(i,QHeaderView.ResizeMode.Interactive); t.setColumnWidth(i,w)
    for r,row in enumerate(rows):
        for c,value in enumerate(row):
            item=QTableWidgetItem(str(value if value is not None else "—"))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if isinstance(value, tuple):
                item=QTableWidgetItem(value[0]); item.setForeground(QColor(value[1]))
            t.setItem(r,c,item)
    t.resizeRowsToContents()
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
        p.setPen(QColor(TEXT)); p.setFont(QFont("Segoe UI",18,QFont.Weight.Bold)); p.drawText(QRectF(50,78,105,27),Qt.AlignmentFlag.AlignCenter,str(total))
        p.setPen(QColor(MUTED)); p.setFont(QFont("Segoe UI",8)); p.drawText(QRectF(50,104,105,22),Qt.AlignmentFlag.AlignCenter,"ENGAGEMENTS")
        p.end()


class MiniBarChart(QWidget):
    def __init__(self, items, parent=None):
        super().__init__(parent); self.items=items; self.setMinimumHeight(184)
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w=self.width(); left=145; right=w-42; plotw=max(120,right-left); rowh=27
        for i,(name,value,color) in enumerate(self.items):
            y=18+i*rowh
            p.setPen(QColor(MUTED)); p.setFont(QFont("Segoe UI",8)); p.drawText(0,y+12,138,18,Qt.AlignmentFlag.AlignRight,name)
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
        root=QVBoxLayout(self); root.setContentsMargins(26,22,26,24); root.setSpacing(17)
        root.addWidget(PageHeader("Executive portfolio", "A synthetic, evidence-led view of software quality, service stability, and delivery assurance."))
        summary=db.portfolio_summary(); counts=summary["statuses"]
        cards=QHBoxLayout(); cards.setSpacing(12)
        cards.addWidget(KpiCard("ENGAGEMENTS", "28", "5 synthetic business units", BLUE))
        cards.addWidget(KpiCard("RED PRIORITY", str(counts.get("Red",0)), "Verified critical risks", RED))
        cards.addWidget(KpiCard("RELEASE TRACEABILITY", f"{summary['traceable']}/{summary['releases']}", "64% of synthetic sample", AMBER))
        cards.addWidget(KpiCard("ACTIONS OVERDUE", f"{summary['overdue']}/{summary['actions']}", "31% · synthetic baseline", AMBER))
        root.addLayout(cards)
        top=QHBoxLayout(); top.setSpacing(14)
        health,panel_l=panel("Portfolio health", "Case starting mix. Statuses are explained by engagement-level evidence.")
        inner=QHBoxLayout(); inner.addWidget(DonutChart(counts),0)
        legend=QVBoxLayout(); legend.setSpacing(10)
        for s in ("Red","Amber","Green","Unknown"):
            n=counts.get(s,0); row=QHBoxLayout(); row.addWidget(status_badge(s)); row.addStretch(1); row.addWidget(label(str(n),color=STATUS_COLORS[s],bold=True)); legend.addLayout(row)
        legend.addStretch(1); legend.addWidget(label("As of 05 Nov 2026 · all added records are synthetic", "Muted", wrap=True)); inner.addLayout(legend,1); panel_l.addLayout(inner)
        signals,sl=panel("Assurance signals", "Selected portfolio metrics from the supplied exercise inputs.")
        metrics=[("Commitments met",db.average_observation("Commitments met"),TEAL),("SLO compliance",db.average_observation("SLO compliance"),TEAL),("Traceable releases",64,AMBER),("Repeat findings",22,AMBER),("Overdue actions",31,RED)]
        sl.addWidget(MiniBarChart(metrics)); sl.addWidget(label("Green target is >95% for positive percentage measures. Other bands are demo assumptions.","Muted",wrap=True))
        top.addWidget(health,1); top.addWidget(signals,1); root.addLayout(top)
        bottom=QHBoxLayout(); bottom.setSpacing(14)
        risks,rl=panel("Priority engagements", "Select a row to review the evidence and rating rationale.")
        engs=db.get_engagements()
        rows=[]
        for e in engs[:8]: rows.append([e["engagement_id"],e["name"],e["business_unit"],(e["overall_status"],STATUS_COLORS.get(e["overall_status"],MUTED)),e["evidence_confidence"]])
        self.table=make_table(["ID","ENGAGEMENT","BUSINESS UNIT","HEALTH","EVIDENCE"],rows,[92,220,140,95,90],34)
        self.table.cellClicked.connect(self.row_clicked); rl.addWidget(self.table); bottom.addWidget(risks,2)
        plan,pl=panel("30 / 60 / 90 day plan", "Contain risk → strengthen controls → verify sustained outcomes.")
        hcounts=db.action_counts_by_horizon()
        for day,caption,count in [(30,"Stabilize & contain",hcounts.get(30,0)),(60,"Correct & control",hcounts.get(60,0)),(90,"Verify & improve",hcounts.get(90,0))]:
            r=QHBoxLayout(); r.addWidget(label(f"DAY {day}",color=TEAL,bold=True)); r.addWidget(label(caption)); r.addStretch(1); r.addWidget(label(str(count),color=TEXT,bold=True)); pl.addLayout(r)
        pl.addWidget(label("Every accepted action has one accountable owner, a due date, an outcome, and closure evidence.","Muted",wrap=True)); bottom.addWidget(plan,1)
        root.addLayout(bottom,1)
    def row_clicked(self,row,col):
        item=self.table.item(row,0)
        if item: self.open_detail(item.text())


class EngagementsPage(QWidget):
    def __init__(self, open_detail):
        super().__init__(); self.open_detail=open_detail
        root=QVBoxLayout(self); root.setContentsMargins(26,22,26,24); root.setSpacing(15)
        root.addWidget(PageHeader("Engagements", "Filter the portfolio and open an engagement to inspect its health dimensions and evidence."))
        filters=QHBoxLayout(); self.search=QLineEdit(); self.search.setPlaceholderText("Search ID, synthetic name, or unit")
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
            p2,l2=panel("Linked actions", "Action records remain synthetic and have one accountable owner.")
            for a in selected:
                row=QHBoxLayout(); row.addWidget(label(f"{a['action_id']} · {a['title']}",bold=True,wrap=True),2); row.addWidget(label(f"{a['owner']}  ·  Day {a['horizon']}",color=TEAL,wrap=True),1); row.addWidget(status_badge(a["status"])); l2.addLayout(row)
            root.addWidget(p2)


class RecommendationCard(QFrame):
    def __init__(self,rec,refresh):
        super().__init__(); self.setObjectName("Panel")
        l=QVBoxLayout(self); l.setContentsMargins(17,15,17,15); l.setSpacing(9)
        top=QHBoxLayout(); top.addWidget(label(f"{rec['recommendation_id']}  ·  {rec['engagement_name']}",color=TEAL,bold=True)); top.addStretch(1); top.addWidget(status_badge(rec["priority"])); l.addLayout(top)
        l.addWidget(label(rec["title"],size=12,bold=True,wrap=True)); l.addWidget(label(rec["rationale"],"Muted",wrap=True))
        facts=QHBoxLayout(); facts.addWidget(label(f"Owner role: {rec['owner']}",color=BLUE)); facts.addWidget(label(f"Horizon: Day {rec['horizon']}",color=TEAL)); facts.addWidget(label(f"Confidence: {rec['confidence']}",color=AMBER)); facts.addStretch(1); l.addLayout(facts)
        source=("Seeded synthetic demo draft" if rec["model_name"]=="Seeded synthetic draft" else f"Live model draft · {rec['model_name']} · synthetic context")
        l.addWidget(label(f"Evidence reference: {rec['trigger_ref']}  ·  {source}  ·  Human review required",color=MUTED,size=8,wrap=True))
        if rec["assumptions"]: l.addWidget(label(f"Assumptions / uncertainty: {rec['assumptions']}",color=AMBER,size=8,wrap=True))
        actions=QHBoxLayout(); actions.addStretch(1)
        if rec["status"]=="Pending":
            edit=QPushButton("Edit draft"); edit.clicked.connect(lambda: self.edit(rec,refresh))
            accept=QPushButton("Accept & create action"); accept.setObjectName("Primary"); accept.clicked.connect(lambda: self.approve(rec["recommendation_id"],refresh))
            reject=QPushButton("Reject draft"); reject.setObjectName("Danger"); reject.clicked.connect(lambda: self.reject(rec["recommendation_id"],refresh))
            actions.addWidget(edit); actions.addWidget(reject); actions.addWidget(accept)
        else: actions.addWidget(status_badge(rec["status"]))
        l.addLayout(actions)
    def edit(self,rec,refresh):
        dialog=QDialog(self); dialog.setWindowTitle("Edit AI action draft"); dialog.setMinimumWidth(520)
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


class RecommendationWorker(QThread):
    generated = Signal(str, dict)
    failed = Signal(str)
    def __init__(self, engagement_id):
        super().__init__(); self.engagement_id=engagement_id
    def run(self):
        try:
            context=db.get_ai_context(self.engagement_id)
            result=ai_provider.generate_recommendation(context)
            self.generated.emit(self.engagement_id,result)
        except Exception as exc:
            self.failed.emit(str(exc))


class RecommendationsPage(QWidget):
    def __init__(self): super().__init__(); self.worker=None; self.build()
    def build(self):
        root=QVBoxLayout(self); root.setContentsMargins(26,22,26,24); root.setSpacing(14)
        provider_text=(f"Live provider ready · {ai_provider.provider_label()} · synthetic context only" if ai_provider.provider_ready() else "Demo drafts available · configure OPENAI_API_KEY and OPENAI_MODEL to enable live AI")
        root.addWidget(PageHeader("AI recommendation review", provider_text))
        live_row=QHBoxLayout(); self.engagement_picker=QComboBox()
        for e in db.get_engagements(): self.engagement_picker.addItem(f"{e['engagement_id']} · {e['name']}",e['engagement_id'])
        self.generate_button=QPushButton("Generate live AI draft"); self.generate_button.setObjectName("Primary")
        self.generate_button.setEnabled(ai_provider.provider_ready()); self.generate_button.clicked.connect(self.generate_live)
        self.live_status=label("Live model is optional. No credentials are stored in this app.","Muted",wrap=True)
        live_row.addWidget(self.engagement_picker,2); live_row.addWidget(self.generate_button); live_row.addWidget(self.live_status,2); root.addLayout(live_row)
        banner,p=panel("Human approval is required", "Metric calculations and health statuses come from configured rules. A reviewer must accept, edit, or reject every recommendation before an action is assigned.")
        p.addWidget(label("Facts and hypotheses must be distinguished; insufficient evidence should trigger a request for evidence rather than an invented cause.","Muted",wrap=True)); root.addWidget(banner)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); content=QWidget(); v=QVBoxLayout(content); v.setSpacing(11)
        recs=db.get_recommendations("All")
        for rec in recs: v.addWidget(RecommendationCard(rec,self.reload))
        v.addStretch(1); scroll.setWidget(content); root.addWidget(scroll,1)
        self.root_layout=root; self.scroll=scroll
    def reload(self):
        old=self.scroll.widget()
        content=QWidget(); v=QVBoxLayout(content); v.setSpacing(11)
        for rec in db.get_recommendations("All"): v.addWidget(RecommendationCard(rec,self.reload))
        v.addStretch(1); self.scroll.setWidget(content)
        if old: old.deleteLater()
    def generate_live(self):
        if not ai_provider.provider_ready(): return
        eid=self.engagement_picker.currentData()
        self.generate_button.setEnabled(False); self.live_status.setText("Generating a draft from synthetic engagement evidence…")
        self.worker=RecommendationWorker(eid)
        self.worker.generated.connect(self.on_generated); self.worker.failed.connect(self.on_failed)
        self.worker.finished.connect(lambda:self.generate_button.setEnabled(ai_provider.provider_ready()))
        self.worker.start()
    def on_generated(self,eid,result):
        try:
            db.save_ai_recommendation(eid,result)
            self.live_status.setText(f"Live draft created for {eid}. Review evidence references before approval.")
            self.reload()
        except Exception as exc: self.on_failed(str(exc))
    def on_failed(self,message): self.live_status.setText(f"Draft not saved: {message}")


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
            table=make_table(["ACTION","ENGAGEMENT","ACTION","ACCOUNTABLE OWNER","DUE","STATUS","SUCCESS MEASURE"],rows,[100,105,220,190,100,100,210],44)
            table.cellDoubleClicked.connect(lambda r,c, t=table: self.edit_action(t,r))
            vl.addWidget(label("Double-click a row to update its tracking status.","Muted")); vl.addWidget(table)
            tabs.addTab(widget,f"Day {day} · {len(actions)} actions")
        root.addWidget(tabs,1)
        root.addWidget(label("Completion is owner-reported; effectiveness becomes verified only after a reviewer checks the evidence.","Muted",wrap=True))
    def edit_action(self,table,row):
        item=table.item(row,0)
        if not item:return
        action_id=item.text()
        dlg=QMessageBox(self); dlg.setWindowTitle("Update synthetic action")
        dlg.setText(f"Choose a new status for {action_id}.")
        opts={"Open":dlg.addButton("Open",QMessageBox.ButtonRole.ActionRole),
              "In progress":dlg.addButton("In progress",QMessageBox.ButtonRole.ActionRole),
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
        root.addWidget(PageHeader("Evidence & findings", "Inspect the synthetic release sample and quality/service findings supporting portfolio signals."))
        s=db.portfolio_summary()
        p,l=panel("Sample integrity", f"{s['traceable']} of {s['releases']} sampled releases fully traceable (64%) · {s['repeats']} of {s['findings']} findings marked repeat (22%). All records synthetic.")
        l.addWidget(label("Missing evidence is displayed as an evidence gap. It does not, by itself, establish poor service or delivery performance.","Muted",wrap=True)); root.addWidget(p)
        tabs=QTabWidget()
        release_rows=[]
        for r in db.get_releases():
            trace="Traceable" if r["fully_traceable"] else "Gap"
            failed="Yes" if r["failed"] else "No"
            release_rows.append([r["release_id"],r["engagement_id"],r["engagement_name"],r["release_date"],failed,(trace,TEAL if trace=="Traceable" else AMBER),f"A:{r['approval_evidence']} · T:{r['test_evidence']} · C:{r['change_evidence']}",r["evidence_ref"]])
        rt=make_table(["RELEASE","ENGAGEMENT ID","ENGAGEMENT","DATE","FAILED","TRACEABILITY","APPROVAL / TEST / CHANGE","SYNTHETIC EVIDENCE REF"],release_rows,[90,110,170,105,70,105,160,170],38)
        findings=[]
        for f in db.get_findings(50): findings.append([f["finding_id"],f["engagement_id"],f["engagement_name"],f["category"],(f["severity"],STATUS_COLORS.get(f["severity"],MUTED)),"Yes" if f["repeat_flag"] else "No",f["customer_impact"],f["finding_date"],f["summary"]])
        ft=make_table(["FINDING","ENGAGEMENT ID","ENGAGEMENT","CATEGORY","SEVERITY","REPEAT","IMPACT","DATE","SYNTHETIC SUMMARY"],findings,[90,105,160,130,90,70,90,100,250],38)
        rp=QWidget(); rl=QVBoxLayout(rp); rl.addWidget(rt)
        fp=QWidget(); fl=QVBoxLayout(fp); fl.addWidget(ft)
        tabs.addTab(rp,"Release samples · 25"); tabs.addTab(fp,"Findings · 50")
        root.addWidget(tabs,1)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("Delivery Assurance Executive App · Synthetic Demo"); self.resize(1500,960); self.setMinimumSize(1180,760)
        shell=QWidget(); layout=QHBoxLayout(shell); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
        sidebar=QFrame(); sidebar.setObjectName("Sidebar"); sidebar.setFixedWidth(230); sl=QVBoxLayout(sidebar); sl.setContentsMargins(17,22,17,18); sl.setSpacing(7)
        sl.addWidget(label("ASSURANCE",color=TEAL,size=9,bold=True)); sl.addWidget(label("Delivery\nIntelligence",size=18,bold=True)); sl.addSpacing(13)
        sl.addWidget(label("WORKSPACE",color=MUTED,size=8,bold=True))
        self.stack=QStackedWidget(); self.pages={}; self.nav_buttons={}
        nav_items=[("dashboard","Executive portfolio"),("engagements","Engagements"),("recommendations","AI recommendations"),("plan","30 / 60 / 90 plan"),("evidence","Evidence & findings")]
        for key,title in nav_items:
            b=QPushButton(title); b.setCheckable(True); b.setCursor(Qt.CursorShape.PointingHandCursor); b.clicked.connect(lambda checked=False,k=key:self.navigate(k)); b.setMinimumHeight(39); sl.addWidget(b); self.nav_buttons[key]=b
        sl.addStretch(1)
        ai_line=(f"Live model: {ai_provider.provider_label()}" if ai_provider.provider_ready() else "Live AI not configured")
        info,p=panel("DEMO DATA", f"Synthetic only\nAs of 05 Nov 2026\n{ai_line}")
        info.setStyleSheet("QFrame#Panel { background:#131c26; border:1px solid #304153; border-radius:12px; }")
        for i in range(p.count()):
            w=p.itemAt(i).widget()
            if isinstance(w,QLabel): w.setStyleSheet(f"color:{MUTED}; font-size:8pt")
        sl.addWidget(info)
        layout.addWidget(sidebar)
        content=QWidget(); cl=QVBoxLayout(content); cl.setContentsMargins(0,0,0,0); cl.setSpacing(0)
        top=QFrame(); top.setFixedHeight(54); top.setStyleSheet("background:#0e151e;border-bottom:1px solid #263443;")
        tl=QHBoxLayout(top); tl.setContentsMargins(22,0,22,0); tl.addWidget(label("SUPER SENIOR DELIVERY ASSURANCE",color=MUTED,size=8,bold=True)); tl.addStretch(1); tl.addWidget(label("SYNTHETIC CASE  ·  05 NOV 2026",color=TEAL,size=8,bold=True)); cl.addWidget(top)
        self.stack.setObjectName("MainStack"); cl.addWidget(self.stack,1); layout.addWidget(content,1)
        self.setCentralWidget(shell)
        db.init_db(); self.build_pages(); self.navigate("dashboard")
    def build_pages(self):
        self.pages={
          "dashboard":DashboardPage(self.open_detail),
          "engagements":EngagementsPage(self.open_detail),
          "recommendations":RecommendationsPage(),
          "plan":PlanPage(),
          "evidence":EvidencePage(),
        }
        while self.stack.count():
            old=self.stack.widget(0)
            self.stack.removeWidget(old)
            old.deleteLater()
        for key in ("dashboard","engagements","recommendations","plan","evidence"):
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
    app=QApplication(sys.argv); app.setStyle("Fusion"); app.setStyleSheet(APP_STYLE)
    win=MainWindow(); win.show(); sys.exit(app.exec())

if __name__=="__main__": main()

