<template>
  <div class="aot-page">

    <!-- ── Header ── -->
    <div class="aot-header">
      <div class="aot-header-title">AOT Sales Dashboard</div>
      <div class="aot-header-right">
        <span v-if="asOf" class="aot-as-of">As of: {{ asOf }}</span>
        <button class="aot-btn aot-btn-refresh" @click="refresh" :disabled="loading">
          <span v-if="loading" class="aot-spin"></span>
          <span v-else>↻ Refresh</span>
        </button>
      </div>
    </div>

    <!-- ── Tab bar ── -->
    <div class="aot-tab-bar">
      <button v-for="t in TABS" :key="t.id" class="aot-tab" :class="{ active: activeTab === t.id }" @click="activeTab = t.id">
        {{ t.label }}
      </button>
    </div>

    <!-- ── Content area ── -->
    <div class="aot-content">

      <!-- Loading -->
      <div v-if="loading && !snapshot" class="aot-empty">
        <div class="aot-spinner"></div>
        <div class="aot-empty-txt">Loading dashboard…</div>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="aot-error">
        <div class="aot-error-icon">⚠</div>
        <div>{{ error }}</div>
        <button class="aot-btn aot-btn-refresh" style="margin-top:12px" @click="refresh">Retry</button>
      </div>

      <!-- ── Snapshot Tab (Tab 1) ── -->
      <template v-else-if="activeTab === 'snapshot' && snapshot">

        <!-- Period pill selector -->
        <div class="aot-pills">
          <button v-for="p in PERIODS" :key="p.id" class="aot-pill" :class="{ active: activePeriod === p.id }" @click="selectPeriod(p.id)">
            {{ p.label }}
          </button>
        </div>

        <!-- KPI strip -->
        <div class="aot-kpi-strip">
          <div v-for="card in kpiCards" :key="card.key" class="aot-kpi-card">
            <div class="aot-kpi-label">{{ card.label }}</div>
            <div class="aot-kpi-value">{{ card.value }}</div>
            <div :class="['aot-growth', growthClass(card.growth)]">{{ growthLabel(card.growth) }}</div>
          </div>
        </div>

        <!-- 5 period sections stacked -->
        <div v-for="p in PERIODS" :key="p.id" :ref="el => { if (el) periodEls[p.id] = el }" class="aot-period-section">

          <!-- Section header -->
          <div class="aot-section-hd">
            <span class="aot-section-label">{{ snapshot[p.id].label }}</span>
            <span class="aot-section-dates">
              <span class="aot-cy-label">{{ snapshot[p.id].cy_label }}</span>
              <span class="aot-vs">vs</span>
              <span class="aot-ly-label">{{ snapshot[p.id].ly_label }}</span>
            </span>
          </div>

          <!-- Two tables side by side -->
          <div class="aot-table-pair">

            <!-- Revenue table -->
            <div class="aot-table-card">
              <div class="aot-table-title">Net Revenue (₹ Cr)</div>
              <div class="aot-table-scroll">
                <table class="aot-table">
                  <thead>
                    <tr>
                      <th class="col-row">Row</th>
                      <th class="col-num">{{ snapshot[p.id].cy_col }}</th>
                      <th class="col-num">{{ snapshot[p.id].ly_col }}</th>
                      <th class="col-grw">Grwth</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in snapshot[p.id].rows" :key="row.key" :class="['tr-' + row.key, { 'tr-indent': row.indent }]">
                      <td class="col-row" :class="{ 'td-indent': row.indent }">{{ row.label }}</td>
                      <td class="col-num">{{ fmtCr(row.cy_rev) }}</td>
                      <td class="col-num col-ly">{{ fmtCr(row.ly_rev) }}</td>
                      <td class="col-grw">
                        <span :class="['badge', growthClass(row.growth_rev)]">{{ growthLabel(row.growth_rev) }}</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <!-- Qty table -->
            <div class="aot-table-card">
              <div class="aot-table-title">Sales Qty</div>
              <div class="aot-table-scroll">
                <table class="aot-table">
                  <thead>
                    <tr>
                      <th class="col-row">Row</th>
                      <th class="col-num">{{ snapshot[p.id].cy_col }}</th>
                      <th class="col-num">{{ snapshot[p.id].ly_col }}</th>
                      <th class="col-grw">Grwth</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in snapshot[p.id].rows" :key="row.key" :class="['tr-' + row.key, { 'tr-indent': row.indent }]">
                      <td class="col-row" :class="{ 'td-indent': row.indent }">{{ row.label }}</td>
                      <td class="col-num">{{ fmtQty(row.cy_qty) }}</td>
                      <td class="col-num col-ly">{{ fmtQty(row.ly_qty) }}</td>
                      <td class="col-grw">
                        <span :class="['badge', growthClass(row.growth_qty)]">{{ growthLabel(row.growth_qty) }}</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

          </div><!-- /table-pair -->
        </div><!-- /period-section -->
      </template>

      <!-- ── Other tabs placeholder ── -->
      <div v-else-if="activeTab !== 'snapshot'" class="aot-coming-soon">
        <div class="aot-coming-icon">📊</div>
        <div class="aot-coming-title">{{ TABS.find(t => t.id === activeTab)?.label }} — Coming Soon</div>
        <div class="aot-coming-sub">This tab is under development.</div>
      </div>

    </div><!-- /content -->
  </div>
</template>

<script setup>
import { ref, reactive, computed, nextTick, onMounted } from 'vue';

// ── Constants ─────────────────────────────────────────────────────────────────

const TABS = [
  { id: 'snapshot', label: 'Snapshot' },
  { id: 'brand',    label: 'Brand Summary' },
  { id: 'store',    label: 'Store Summary' },
  { id: 'customer', label: 'Customer Summary' },
];

const PERIODS = [
  { id: 'daily',  label: 'Daily' },
  { id: 'weekly', label: 'Weekly' },
  { id: 'mtd',    label: 'MTD' },
  { id: 'qtd',    label: 'QTD' },
  { id: 'ytd',    label: 'YTD' },
];

// ── Props ─────────────────────────────────────────────────────────────────────

const props = defineProps({ page: { type: Object, default: null } });

// ── State ─────────────────────────────────────────────────────────────────────

const activeTab     = ref('snapshot');
const activePeriod  = ref('daily');
const loading       = ref(false);
const error         = ref(null);
const dashboardData = ref(null);
const periodEls     = reactive({});

// ── Derived ───────────────────────────────────────────────────────────────────

const snapshot = computed(() => dashboardData.value?.snapshot ?? null);
const asOf     = computed(() => dashboardData.value?.as_of ?? '');

const kpiCards = computed(() => {
  if (!snapshot.value) return [];
  const pd = snapshot.value[activePeriod.value];
  if (!pd) return [];
  const row = (key) => pd.rows.find(r => r.key === key) || {};
  const net = row('net_revenue');
  const b2c = row('b2c');
  const hv  = row('high_value');
  return [
    { key: 'net_rev', label: 'Net Revenue',        value: fmtCr(net.cy_rev),  growth: net.growth_rev },
    { key: 'net_qty', label: 'Net Qty',             value: fmtQty(net.cy_qty), growth: net.growth_qty },
    { key: 'b2c_rev', label: 'B2C Revenue',         value: fmtCr(b2c.cy_rev),  growth: b2c.growth_rev },
    { key: 'b2c_qty', label: 'B2C Qty',             value: fmtQty(b2c.cy_qty), growth: b2c.growth_qty },
    { key: 'hv_rev',  label: 'High Value Revenue',  value: fmtCr(hv.cy_rev),   growth: hv.growth_rev },
    { key: 'hv_qty',  label: 'High Value Qty',      value: fmtQty(hv.cy_qty),  growth: hv.growth_qty },
  ];
});

// ── Formatters ────────────────────────────────────────────────────────────────

function fmtCr(v) {
  if (v == null || isNaN(v)) return '—';
  return '₹' + (v / 1e7).toFixed(2) + ' Cr';
}

function fmtQty(v) {
  if (v == null || isNaN(v)) return '—';
  return Math.round(v).toLocaleString('en-IN');
}

function growthLabel(v) {
  if (v == null) return '—';
  const pct = Math.abs(v * 100).toFixed(1);
  return v >= 0 ? `▲ ${pct}%` : `▼ ${pct}%`;
}

function growthClass(v) {
  if (v == null) return 'g-na';
  return v >= 0 ? 'g-pos' : 'g-neg';
}

// ── Actions ───────────────────────────────────────────────────────────────────

function selectPeriod(id) {
  activePeriod.value = id;
  nextTick(() => {
    const el = periodEls[id];
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
}

const call = (method) => new Promise((resolve, reject) =>
  frappe.call({ method, callback: r => resolve(r?.message), error: reject })
);

async function refresh() {
  loading.value = true;
  error.value = null;
  try {
    dashboardData.value = await call('aetas_customization.aetas_customization.aot_data.get_dashboard_data');
  } catch (err) {
    error.value = err?.message || 'Failed to load dashboard data.';
  } finally {
    loading.value = false;
  }
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────

onMounted(() => {
  refresh();
});
</script>

<style scoped>
/* ── Shell ── */
.aot-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  background: #f4f7f9;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  color: #1e293b;
}

/* ── Header ── */
.aot-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: #ffffff;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
  gap: 12px;
  flex-wrap: wrap;
}

.aot-header-title {
  font-size: 1.2rem;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: -0.01em;
}

.aot-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.aot-as-of {
  font-size: 0.8rem;
  color: #64748b;
  font-weight: 500;
}

.aot-btn {
  padding: 7px 16px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
  color: #334155;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition: background 0.15s;
}
.aot-btn:hover { background: #f1f5f9; }
.aot-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.aot-btn-refresh { }

.aot-spin {
  width: 14px; height: 14px;
  border: 2px solid #cbd5e1;
  border-top-color: #6366f1;
  border-radius: 50%;
  animation: aot-spin 0.8s linear infinite;
  display: inline-block;
}

/* ── Tab bar ── */
.aot-tab-bar {
  display: flex;
  gap: 0;
  background: #ffffff;
  border-bottom: 2px solid #e2e8f0;
  padding: 0 24px;
  flex-shrink: 0;

}

.aot-tab {
  padding: 12px 20px;
  border: none;
  background: transparent;
  font-size: 0.875rem;
  font-weight: 600;
  color: #64748b;
  cursor: pointer;
  border-bottom: 3px solid transparent;
  margin-bottom: -2px;
  white-space: nowrap;
  transition: color 0.15s, border-color 0.15s;
}
.aot-tab:hover { color: #0f172a; }
.aot-tab.active { color: #6366f1; border-bottom-color: #6366f1; }

/* ── Content ── */
.aot-content {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  padding: 0 24px 40px;
}

/* ── Empty / Loading / Error ── */
.aot-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  gap: 12px;
}

.aot-spinner {
  width: 40px; height: 40px;
  border: 4px solid #e2e8f0;
  border-top-color: #6366f1;
  border-radius: 50%;
  animation: aot-spin 0.8s linear infinite;
}

.aot-empty-txt { color: #64748b; font-weight: 600; }

.aot-error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 12px;
  padding: 24px;
  text-align: center;
  color: #b91c1c;
  font-weight: 600;
}
.aot-error-icon { font-size: 2rem; margin-bottom: 8px; }

/* ── Period pills ── */
.aot-pills {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  background: #f4f7f9;
  padding: 16px 0 12px;
  margin-bottom: 8px;
}

.aot-pill {
  padding: 6px 16px;
  border: 1px solid #e2e8f0;
  border-radius: 20px;
  background: #ffffff;
  font-size: 0.8rem;
  font-weight: 600;
  color: #475569;
  cursor: pointer;
  transition: all 0.15s;
}
.aot-pill:hover { background: #f1f5f9; }
.aot-pill.active {
  background: #6366f1;
  border-color: #6366f1;
  color: #ffffff;
}

/* ── KPI strip ── */
.aot-kpi-strip {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 28px;
}

.aot-kpi-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px 20px;
}

.aot-kpi-label {
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #64748b;
  margin-bottom: 6px;
}

.aot-kpi-value {
  font-size: 1.25rem;
  font-weight: 800;
  color: #0f172a;
  margin-bottom: 4px;
}

.aot-growth { font-size: 0.82rem; font-weight: 700; }

/* ── Period section ── */
.aot-period-section {
  margin-bottom: 32px;
  scroll-margin-top: 20px;
}

.aot-section-hd {
  display: flex;
  align-items: baseline;
  gap: 12px;
  padding: 10px 0 10px;
  border-top: 2px solid #e2e8f0;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.aot-section-label {
  font-size: 0.8rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #334155;
}

.aot-section-dates {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.78rem;
}

.aot-cy-label { font-weight: 700; color: #1e293b; }
.aot-vs       { color: #94a3b8; font-size: 0.7rem; }
.aot-ly-label { font-weight: 500; color: #94a3b8; }

/* ── Table pair ── */
.aot-table-pair {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.aot-table-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
}

.aot-table-title {
  padding: 10px 14px 8px;
  font-size: 0.78rem;
  font-weight: 700;
  color: #475569;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
}

.aot-table-scroll {
  overflow: visible;
}

/* ── Table ── */
.aot-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
}

.aot-table thead th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: #f8fafc;
  padding: 8px 12px;
  text-align: right;
  font-size: 0.72rem;
  font-weight: 700;
  color: #64748b;
  border-bottom: 1px solid #e2e8f0;
  white-space: nowrap;
}
.aot-table thead th.col-row { text-align: left; }

.aot-table tbody td {
  padding: 7px 12px;
  text-align: right;
  border-bottom: 1px solid #f1f5f9;
  white-space: nowrap;
  color: #1e293b;
}
.aot-table tbody td.col-row { text-align: left; }
.aot-table tbody td.td-indent {
  padding-left: 26px;
  font-weight: 400;
}
.aot-table tbody td.col-ly { color: #64748b; }

.aot-table tbody tr:last-child td { border-bottom: none; }

/* ── Net Revenue row ── */
.aot-table tbody tr.tr-net_revenue td {
  font-weight: 800;
  background: #f0f9ff;
  color: #0c4a6e;
  border-bottom: 2px solid #bae6fd;
}
.aot-table tbody tr.tr-net_revenue td.col-ly { color: #38bdf8; }

/* ── B2C section header ── */
.aot-table tbody tr.tr-b2c td {
  font-weight: 700;
  background: #eff6ff;
  color: #1d4ed8;
  border-top: 2px solid #bfdbfe;
  border-bottom: 1px solid #dbeafe;
}
.aot-table tbody tr.tr-b2c td.col-ly { color: #93c5fd; }

/* ── B2C children ── */
.aot-table tbody tr.tr-b2c_watches td,
.aot-table tbody tr.tr-b2c_accessories td,
.aot-table tbody tr.tr-b2c_services td {
  background: #f8faff;
  color: #334155;
}
.aot-table tbody tr.tr-b2c_watches td.col-ly,
.aot-table tbody tr.tr-b2c_accessories td.col-ly,
.aot-table tbody tr.tr-b2c_services td.col-ly { color: #94a3b8; }

/* ── High Value section header ── */
.aot-table tbody tr.tr-high_value td {
  font-weight: 700;
  background: #faf5ff;
  color: #6d28d9;
  border-top: 2px solid #ddd6fe;
  border-bottom: 1px solid #ede9fe;
}
.aot-table tbody tr.tr-high_value td.col-ly { color: #c4b5fd; }

/* ── High Value children ── */
.aot-table tbody tr.tr-hv_watches td,
.aot-table tbody tr.tr-hv_accessories td,
.aot-table tbody tr.tr-hv_services td {
  background: #fdfbff;
  color: #334155;
}
.aot-table tbody tr.tr-hv_watches td.col-ly,
.aot-table tbody tr.tr-hv_accessories td.col-ly,
.aot-table tbody tr.tr-hv_services td.col-ly { color: #94a3b8; }

.col-row  { width: 45%; }
.col-num  { width: 20%; }
.col-grw  { width: 15%; }

/* ── Growth badges ── */
.badge       { padding: 2px 6px; border-radius: 4px; font-size: 0.72rem; font-weight: 700; }
.badge.g-pos { background: #dcfce7; color: #15803d; }
.badge.g-neg { background: #fee2e2; color: #b91c1c; }
.badge.g-na  { color: #94a3b8; }

.aot-growth.g-pos { color: #16a34a; }
.aot-growth.g-neg { color: #dc2626; }
.aot-growth.g-na  { color: #94a3b8; }

/* ── Coming soon ── */
.aot-coming-soon {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  gap: 10px;
  text-align: center;
}
.aot-coming-icon  { font-size: 2.5rem; }
.aot-coming-title { font-size: 1.1rem; font-weight: 700; color: #334155; }
.aot-coming-sub   { font-size: 0.9rem; color: #94a3b8; }

/* ── Responsive ── */
@media (max-width: 1279px) {
  .aot-kpi-strip { grid-template-columns: repeat(3, 1fr); }
  .aot-table { font-size: 0.75rem; }
}

@media (max-width: 900px) {
  .aot-kpi-strip { grid-template-columns: repeat(2, 1fr); }
  .aot-table-pair { grid-template-columns: 1fr; }
  .aot-content { padding: 16px 16px 40px; }
}

@media (max-width: 640px) {
  .aot-kpi-strip { grid-template-columns: 1fr; }
  .aot-header { padding: 12px 16px; }
  .aot-tab-bar { padding: 0 12px; }
  .aot-tab { padding: 10px 14px; }
}

@keyframes aot-spin { to { transform: rotate(360deg); } }
</style>
