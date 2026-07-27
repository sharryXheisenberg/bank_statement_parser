from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

OUT = "/home/claude/bank_statement_parser/sample_pdfs/sbi_sample.pdf"

COLS = {
    "Txn Date": 40,
    "Value Date": 95,
    "Description": 150,
    "Ref No./Cheque No.": 330,
    "Debit": 430,
    "Credit": 480,
    "Balance": 535,
}

ROWS = [
    ("01/06/24", "01/06/24", "IMPS-GROCERY-BIGBASKET", "S998877", "1,250.00", "", "45,750.00"),
    ("03/06/24", "03/06/24", "SALARY CREDIT MAY", "S998878", "", "60,000.00", "1,05,750.00"),
    ("06/06/24", "06/06/24", "NEFT-INSURANCE-LIC PREM", "S998879", "8,400.00", "", "97,350.00"),
]

c = canvas.Canvas(OUT, pagesize=A4)
width, height = A4
c.setFont("Helvetica-Bold", 14)
c.drawString(40, height - 40, "STATE BANK OF INDIA")
c.setFont("Helvetica", 9)
c.drawString(40, height - 55, "Account Statement")
c.drawString(40, height - 68, "IFSC: SBIN0012345    Account No: XXXXXXXX5678")

y = height - 110
c.setFont("Helvetica-Bold", 8)
for label, x in COLS.items():
    c.drawString(x, y, label)

c.setFont("Helvetica", 8)
y -= 18
for row in ROWS:
    for (label, x), value in zip(COLS.items(), row):
        c.drawString(x, y, value)
    y -= 16

c.save()
print("wrote", OUT)
