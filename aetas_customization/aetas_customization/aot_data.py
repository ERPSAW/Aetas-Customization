import frappe
from datetime import date, timedelta


# ── Defaults ──────────────────────────────────────────────────────────────────

DEFAULT_CATEGORY_MAP = {
    'Watches': 'Watches',
    'Watch Service': 'Services',
    'Jewelry': 'Accessories',
    'Jewellery': 'Accessories',
    'Accessories': 'Accessories',
    'Strap': 'Accessories',
}


# ── Config loader ─────────────────────────────────────────────────────────────

def get_config():
    try:
        doc = frappe.get_single('AOT Dashboard Config')
        cat_map  = {r.item_group: r.category_label for r in (doc.category_mapping or [])}
        hv_ids   = {r.customer for r in (doc.high_end_customers or []) if r.customer}
        ex_ids   = {r.customer for r in (doc.removed_customers or []) if r.customer}
        return {
            'category_map':      cat_map or DEFAULT_CATEGORY_MAP,
            'hv_customers':      hv_ids,
            'exclude_customers': ex_ids,
        }
    except Exception:
        return {
            'category_map':      DEFAULT_CATEGORY_MAP,
            'hv_customers':      set(),
            'exclude_customers': set(),
        }


# ── Period date ranges ────────────────────────────────────────────────────────

def _safe_ly(d):
    try:
        return d.replace(year=d.year - 1)
    except ValueError:
        return d.replace(year=d.year - 1, day=28)


def get_periods():
    today     = date.today()
    yesterday = today - timedelta(days=1)

    # Weekly: last complete week (Mon–Sun) vs the week before it (Mon–Sun)
    last_sun      = today - timedelta(days=today.weekday() + 1)   # Sunday just passed
    last_mon      = last_sun  - timedelta(days=6)                  # Monday of that week
    prev_week_sun = last_mon  - timedelta(days=1)                  # Sunday before that
    prev_week_mon = prev_week_sun - timedelta(days=6)              # Monday of that week

    # MTD: 1st of current month
    mtd_start = today.replace(day=1)

    # Indian FY: starts April 1
    fy_year = today.year if today.month >= 4 else today.year - 1

    # QTD: start of current Indian FY quarter
    m = today.month
    if m in (4, 5, 6):
        q_start = date(fy_year, 4, 1)
    elif m in (7, 8, 9):
        q_start = date(fy_year, 7, 1)
    elif m in (10, 11, 12):
        q_start = date(fy_year, 10, 1)
    else:
        q_start = date(today.year, 1, 1)

    # YTD: April 1 of current Indian FY
    ytd_start = date(fy_year, 4, 1)

    def fmt(d):
        return d.strftime('%-d %b %Y')

    def short(d):
        return d.strftime('%-d %b\'%y')

    cy_yr = today.year
    ly_yr = today.year - 1

    # Quarter label helper
    q_labels = {4: 'Q1', 7: 'Q2', 10: 'Q3', 1: 'Q4'}
    q_label  = q_labels.get(q_start.month, 'Q')

    # Weekly column header: "5–11 May'26" or just "11 May'26" if week started today
    def wk_col(start, end):
        if start == end:
            return short(end)
        return f"{start.strftime('%-d')}–{short(end)}"

    return {
        'daily': {
            'label':    'Daily',
            'cy_start': today,    'cy_end': today,
            'ly_start': yesterday,'ly_end': yesterday,
            'cy_label': fmt(today),
            'ly_label': fmt(yesterday),
            'cy_col':   short(today),
            'ly_col':   short(yesterday),
        },
        'weekly': {
            'label':    'Weekly',
            'cy_start': last_mon,      'cy_end': last_sun,
            'ly_start': prev_week_mon, 'ly_end': prev_week_sun,
            'cy_label': f'{fmt(last_mon)} – {fmt(last_sun)}',
            'ly_label': f'{fmt(prev_week_mon)} – {fmt(prev_week_sun)}',
            'cy_col':   wk_col(last_mon, last_sun),
            'ly_col':   wk_col(prev_week_mon, prev_week_sun),
        },
        'mtd': {
            'label':    'MTD',
            'cy_start': mtd_start,         'cy_end': today,
            'ly_start': _safe_ly(mtd_start),'ly_end': _safe_ly(today),
            'cy_label': f'{fmt(mtd_start)} – {fmt(today)}',
            'ly_label': f'{fmt(_safe_ly(mtd_start))} – {fmt(_safe_ly(today))}',
            'cy_col':   today.strftime('%b\'%y'),
            'ly_col':   _safe_ly(today).strftime('%b\'%y'),
        },
        'qtd': {
            'label':    'QTD',
            'cy_start': q_start,         'cy_end': today,
            'ly_start': _safe_ly(q_start),'ly_end': _safe_ly(today),
            'cy_label': f'{fmt(q_start)} – {fmt(today)}',
            'ly_label': f'{fmt(_safe_ly(q_start))} – {fmt(_safe_ly(today))}',
            'cy_col':   f'{q_label} FY{str(cy_yr)[2:]}',
            'ly_col':   f'{q_label} FY{str(ly_yr)[2:]}',
        },
        'ytd': {
            'label':    'YTD',
            'cy_start': ytd_start,         'cy_end': today,
            'ly_start': _safe_ly(ytd_start),'ly_end': _safe_ly(today),
            'cy_label': f'{fmt(ytd_start)} – {fmt(today)}',
            'ly_label': f'{fmt(_safe_ly(ytd_start))} – {fmt(_safe_ly(today))}',
            'cy_col':   f'FY {cy_yr}-{str(cy_yr + 1)[2:]}',
            'ly_col':   f'FY {ly_yr}-{str(ly_yr + 1)[2:]}',
        },
    }


# ── SQL fetch ─────────────────────────────────────────────────────────────────

def fetch_rows(start_date, end_date, config):
    raw = frappe.db.sql("""
        SELECT
            si.customer,
            si.customer_name,
            sii.item_group,
            SUM(sii.amount) AS amount,
            SUM(sii.qty)    AS qty
        FROM `tabSales Invoice` si
        JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        WHERE si.docstatus = 1
          AND si.is_return  = 0
          AND si.posting_date BETWEEN %(start_date)s AND %(end_date)s
        GROUP BY si.customer, sii.item_group
        ORDER BY si.customer
    """, {'start_date': start_date, 'end_date': end_date}, as_dict=True)

    return _tag(raw, config)


def _tag(rows, config):
    tagged      = []
    hv_ids      = config['hv_customers']
    ex_ids      = config['exclude_customers']
    cat_map     = config['category_map']

    for row in rows:
        customer_id = row.get('customer') or ''

        if customer_id in ex_ids:
            continue

        category = cat_map.get(row.get('item_group') or '')
        if not category:
            continue

        ctype = 'High Value' if customer_id in hv_ids else 'B2C'

        tagged.append({
            'customer':      customer_id,
            'customer_name': row.get('customer_name') or customer_id,
            'item_group':    row['item_group'],
            'category':      category,
            'customer_type': ctype,
            'amount':        float(row.get('amount') or 0),
            'qty':           float(row.get('qty') or 0),
        })
    return tagged


# ── Aggregation ───────────────────────────────────────────────────────────────

def _sum(rows, ctype=None, category=None):
    amt = qty = 0.0
    for r in rows:
        if ctype    and r['customer_type'] != ctype:    continue
        if category and r['category']      != category: continue
        amt += r['amount']
        qty += r['qty']
    return amt, qty


def _growth(cy, ly):
    if ly and ly != 0:
        return round((cy - ly) / abs(ly), 4)
    return None


def _row(key, label, indent, cy_amt, cy_qty, ly_amt, ly_qty):
    return {
        'key':        key,
        'label':      label,
        'indent':     indent,
        'cy_rev':     round(cy_amt, 2),
        'ly_rev':     round(ly_amt, 2),
        'growth_rev': _growth(cy_amt, ly_amt),
        'cy_qty':     int(round(cy_qty)),
        'ly_qty':     int(round(ly_qty)),
        'growth_qty': _growth(cy_qty, ly_qty),
    }


def aggregate_snapshot(cy, ly):
    cy_net,   cy_net_q   = _sum(cy)
    ly_net,   ly_net_q   = _sum(ly)
    cy_b2c,   cy_b2c_q   = _sum(cy, 'B2C')
    ly_b2c,   ly_b2c_q   = _sum(ly, 'B2C')
    cy_b2c_w, cy_b2c_wq  = _sum(cy, 'B2C', 'Watches')
    ly_b2c_w, ly_b2c_wq  = _sum(ly, 'B2C', 'Watches')
    cy_b2c_a, cy_b2c_aq  = _sum(cy, 'B2C', 'Accessories')
    ly_b2c_a, ly_b2c_aq  = _sum(ly, 'B2C', 'Accessories')
    cy_b2c_s, cy_b2c_sq  = _sum(cy, 'B2C', 'Services')
    ly_b2c_s, ly_b2c_sq  = _sum(ly, 'B2C', 'Services')
    cy_hv,    cy_hv_q    = _sum(cy, 'High Value')
    ly_hv,    ly_hv_q    = _sum(ly, 'High Value')
    cy_hv_w,  cy_hv_wq   = _sum(cy, 'High Value', 'Watches')
    ly_hv_w,  ly_hv_wq   = _sum(ly, 'High Value', 'Watches')
    cy_hv_a,  cy_hv_aq   = _sum(cy, 'High Value', 'Accessories')
    ly_hv_a,  ly_hv_aq   = _sum(ly, 'High Value', 'Accessories')
    cy_hv_s,  cy_hv_sq   = _sum(cy, 'High Value', 'Services')
    ly_hv_s,  ly_hv_sq   = _sum(ly, 'High Value', 'Services')

    return [
        _row('net_revenue',    'Net Revenue', 0, cy_net,   cy_net_q,   ly_net,   ly_net_q),
        _row('b2c',            'B2C',         0, cy_b2c,   cy_b2c_q,   ly_b2c,   ly_b2c_q),
        _row('b2c_watches',    'Watches',     1, cy_b2c_w, cy_b2c_wq,  ly_b2c_w, ly_b2c_wq),
        _row('b2c_accessories','Accessories', 1, cy_b2c_a, cy_b2c_aq,  ly_b2c_a, ly_b2c_aq),
        _row('b2c_services',   'Services',    1, cy_b2c_s, cy_b2c_sq,  ly_b2c_s, ly_b2c_sq),
        _row('high_value',     'High Value',  0, cy_hv,    cy_hv_q,    ly_hv,    ly_hv_q),
        _row('hv_watches',     'Watches',     1, cy_hv_w,  cy_hv_wq,   ly_hv_w,  ly_hv_wq),
        _row('hv_accessories', 'Accessories', 1, cy_hv_a,  cy_hv_aq,   ly_hv_a,  ly_hv_aq),
        _row('hv_services',    'Services',    1, cy_hv_s,  cy_hv_sq,   ly_hv_s,  ly_hv_sq),
    ]


# ── Public API ────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_dashboard_data():
    config  = get_config()
    periods = get_periods()
    snapshot = {}

    for pname, pd in periods.items():
        cy_rows = fetch_rows(pd['cy_start'], pd['cy_end'], config)
        ly_rows = fetch_rows(pd['ly_start'], pd['ly_end'], config)
        rows    = aggregate_snapshot(cy_rows, ly_rows)

        snapshot[pname] = {
            'label':    pd['label'],
            'cy_label': pd['cy_label'],
            'ly_label': pd['ly_label'],
            'cy_col':   pd['cy_col'],
            'ly_col':   pd['ly_col'],
            'rows':     rows,
        }

    return {
        'snapshot': snapshot,
        'as_of': frappe.utils.now_datetime().strftime('%-d %b %Y, %I:%M %p'),
    }
