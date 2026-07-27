"""
Generates a fake-but-realistic HDFC statement PDF purely to exercise the
parser end-to-end (no real bank data involved). Mimics HDFC's actual column
positions closely enough that the coordinate-based column detector has
something real to chew on.
"""
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

OUT = "/home/claude/bank_statement_parser/sample_pdfs/hdfc_sample.pdf"

COLS = {
    "Date": 40,
    "Narration": 100,
    "Chq./Ref.No.": 300,
    "Value Dt": 370,
    "Withdrawal Amt.": 430,
    "Deposit Amt.": 500,
    "Closing Balance": 560,
}

ROWS = [
    ("01/06/24", "UPI-SWIGGY-order12345-payment", "N123456789", "01/06/24", "450.00", "", "24,550.00"),
    ("02/06/24", "SALARY CREDIT JUNE TECHCORP PVT LTD",
     "N123456790", "02/06/24", "", "85,000.00", "1,09,550.00"),
    ("03/06/24", "NEFT-RENT-JUNE-LANDLORD SHARMA", "N123456791", "03/06/24", "18,000.00", "", "91,550.00"),
    ("05/06/24", "ATM WDL NATIONAL PARK ROAD BRANCH", "N123456792", "05/06/24", "5,000.00", "", "86,550.00"),
    ("07/06/24", "UPI-AMAZON-refund-order99881", "N123456793", "07/06/24", "", "1,200.00", "87,750.00"),
]

c = canvas.Canvas(OUT, pagesize=A4)
width, height = A4

c.setFont("Helvetica-Bold", 14)
c.drawString(40, height - 40, "HDFC BANK")
c.setFont("Helvetica", 9)
c.drawString(40, height - 55, "Statement of Account")
c.drawString(40, height - 68, "IFSC: HDFC0001234    Account No: XXXXXXXX1234")

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
