from app.core.db import SessionLocal
from app.core.models import Company, FinancialAnnual
from ops import recompute_metrics as rm

db = SessionLocal()
ids = (db.query(Company.id)
         .join(FinancialAnnual, FinancialAnnual.company_id==Company.id)
         .group_by(Company.id).all())
ids = [i[0] for i in ids]
print(f"[metrics] companies to compute: {len(ids)}")
w=0
for i,cid in enumerate(ids,1):
    w += rm.compute_company_metrics(db, cid) or 0
    if i%100==0: db.commit(); print(f"[metrics] {i}/{len(ids)} rows={w}")
db.commit(); db.close()
print(f"[metrics] DONE rows={w}")

