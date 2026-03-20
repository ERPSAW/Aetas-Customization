<template>
  <div class="bd-page">
    <div class="bd-container">

      <div class="bd-card bd-header-card">
        <div class="bd-header-inner">
          <div class="bd-header-left">
            <div class="bd-eyebrow"><span class="bd-eyebrow-pip"></span>Boutique Management</div>
            <div class="bd-title">Day Entry</div>
            <div class="bd-boutique-pill" v-if="selectedBoutique">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>
              {{ selectedBoutique }}
            </div>
          </div>
          <div class="bd-date-box">
            <div class="bd-date-day">{{ todayDayName }}</div>
            <div class="bd-date-val">{{ todayDisplay }}</div>
          </div>
        </div>
      </div>

      <div class="bd-card bd-tl-card">
        <div class="bd-tl-inner">
          <div v-for="t in timeline" :key="t.date" class="bd-tl-pill" :class="[t.cls, t.isToday ? 'is-today' : '']">
            <div class="bd-tl-status-dot" :class="t.cls"></div>
            <span class="bd-tl-date">{{ t.short }}</span>
            <span class="bd-tl-badge">{{ t.isToday ? 'TODAY' : t.badge }}</span>
          </div>
        </div>
      </div>

      <div class="bd-body">

        <div v-if="loading" class="bd-loading bd-card">
          <div class="bd-spinner"></div>
          <div class="bd-loading-txt">Authenticating & Loading...</div>
        </div>

        <div v-else-if="!selectedBoutique" class="bd-empty bd-card">
          <div class="bd-empty-icon" style="margin-bottom: 16px;">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: #94a3b8;"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
          </div>
          <div class="bd-empty-title">Access Denied</div>
          <div class="bd-empty-sub">
            Your user profile is not configured as a manager for any Boutique.<br>
            <i>(Requires: Boutique Manager Role &rarr; Linked in Boutique's "Boutique Manager" field)</i>
          </div>
        </div>

        <template v-else>
          <template v-if="pendingAction === 'all_done'">
            <div class="bd-card c-done bd-content-card" style="cursor:default;">
              <div class="bd-allgood">
                <div class="bd-allgood-icon">
                  <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
                </div>
                <div class="bd-allgood-title">All Caught Up!</div>
                <div class="bd-allgood-sub">
                  Shift completed in <b>{{ shiftDuration(todayEntry.day_started_at, todayEntry.day_ended_at) }}</b>
                </div>

                <div v-if="todayEntry" class="bd-stats">
                  <div class="bd-stat">
                    <div class="bd-stat-val">{{ todayEntry.walk_in || 0 }}</div>
                    <div class="bd-stat-lbl">Walk Ins</div>
                    <div class="bd-stat-micro">
                      <span class="color-indigo">{{ todayEntry.new_customers || 0 }} New</span> &middot; 
                      <span>{{ todayEntry.existing_customers || 0 }} Existing</span>
                    </div>
                  </div>

                  <div class="bd-stat">
                    <div class="bd-stat-val">{{ todayEntry.total_invoices || 0 }}</div>
                    <div class="bd-stat-lbl">Invoices</div>
                    <div class="bd-stat-micro" :class="{ 'color-red': todayEntry.total_invoices !== todayEntry.total_invoices_from_system }">
                      System Logged: {{ todayEntry.total_invoices_from_system || 0 }}
                    </div>
                  </div>

                  <div class="bd-stat">
                      <div class="bd-stat-val g">{{ inr(entryCollections(todayEntry)) }}</div>
                      <div class="bd-stat-lbl">Collections</div>
                      <div class="bd-stat-micro" style="flex-wrap: wrap;">
                          <span>Cash: {{ inr(todayEntry.cash) }}</span> &middot; 
                          <span>CC: {{ inr(todayEntry.cc) }}</span> &middot; 
                          <span>Bank: {{ inr(todayEntry.bank_transfer) }}</span>
                          <template v-if="todayEntry.other > 0">
                          &middot; <span>Other: {{ inr(todayEntry.other) }}</span>
                          </template>
                      </div>
                  </div>

                  <div class="bd-stat">
                    <div class="bd-stat-val p">{{ inr(todayEntry.day_end_petty_cash) }}</div>
                    <div class="bd-stat-lbl">Closing Cash</div>
                    <div class="bd-stat-micro">
                      Opened with {{ inr(todayEntry.day_start_petty_cash) }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>

          <template v-if="pendingAction !== 'all_done'">
            
            <div class="bd-section-lbl" v-if="prevEntry">Action Required — Previous Day</div>
            <div class="bd-section-lbl" v-else style="margin-top:24px;">Today's Entry</div>
            
            <div class="bd-card bd-content-card" :class="todayCardCls">
              
              <div class="bd-card-hd" :class="todayHdCls">
                <div>
                  <div class="bd-card-eyebrow">{{ prevEntry ? 'Previous Day' : 'Today' }}</div>
                  <div class="bd-card-date">{{ fullDate(prevEntry ? prevEntry.date : todayStr) }}</div>
                </div>
                <div class="bd-chip" :class="todayChipCls">{{ todayChipLabel }}</div>
              </div>

              <template v-if="pendingAction === 'start_today'">
                <div class="bd-inner">
                  <div class="bd-inner-hd">
                    <span class="bd-inner-title" style="font-size: 1.1rem;">Day Start</span>
                  </div>
                  <div class="bd-grid bd-g2">
                    <div class="bd-f">
                      <label>Opening Petty Cash <span class="bd-f-hint">(from yesterday)</span></label>
                      <div class="bd-pfx-wrap"><span class="bd-pfx">₹</span><input type="number" class="bd-input has-pfx" v-model.number="sF.petty_cash" min="0" /></div>
                    </div>
                    <div class="bd-f">
                      <label>Remarks <span class="bd-f-hint">(optional)</span></label>
                      <textarea class="bd-ta" v-model="sF.remarks" placeholder="Any notes..."></textarea>
                    </div>
                  </div>
                  <button class="bd-btn bd-btn-start" @click="doStartDay" :disabled="busy">
                    <span v-if="busy"><span class="bd-btn-spin"></span></span>
                    <span v-else>Start Day &rarr;</span>
                  </button>
                </div>
              </template>

              <template v-if="pendingAction === 'end_today' || pendingAction === 'end_previous'">
                
                <div class="bd-inner bg-faint">
                  <div class="bd-inner-hd">
                    <span class="bd-inner-title">Day Start</span><span class="bd-done-badge">✓ Done</span>
                  </div>
                  <div class="bd-ro">
                    <div class="bd-ro-item"><div class="bd-ro-lbl">Opening Cash</div><div class="bd-ro-val accent">{{ inr(activeEntry.day_start_petty_cash) }}</div></div>
                    <div class="bd-ro-item"><div class="bd-ro-lbl">Started At</div><div class="bd-ro-val">{{ hhmm(activeEntry.day_started_at) }}</div></div>
                  </div>
                </div>

                <div class="bd-inner">
                  <div class="bd-inner-hd">
                    <span class="bd-inner-title" style="font-size: 1.1rem;">Day End</span>
                  </div>

                  <div class="bd-fg-title">Customer Count & Invoices</div>
                  <div class="bd-grid bd-g2">
                    <div v-for="f in countFields" :key="f.key" class="bd-metric-block">
                      <div class="bd-metric-top">
                        <label>{{ f.label }}</label>
                        <input type="number" class="bd-input" v-model.number="eF[f.key]" min="0" placeholder="0" />
                      </div>
                      <div class="bd-metric-tools">
                        <input type="text" class="bd-input bd-input-sm" placeholder="Remarks..." v-model="eF[f.key + '_remarks']" />
                      </div>
                    </div>
                  </div>

                  <div class="bd-fg-title">Payments</div>
                  <div class="bd-grid bd-g2">
                    <div v-for="f in paymentFields" :key="f.key" class="bd-metric-block">
                      <div class="bd-metric-top">
                        <label>{{ f.label }}</label>
                        <div class="bd-pfx-wrap">
                          <span class="bd-pfx">₹</span>
                          <input type="number" class="bd-input has-pfx" v-model.number="eF[f.key]" min="0" placeholder="0" />
                        </div>
                      </div>
                      <div class="bd-metric-tools">
                        <input type="text" class="bd-input bd-input-sm" placeholder="Remarks..." v-model="eF[f.key + '_remarks']" />
                        <div class="bd-upload-wrap">
                          <label class="bd-upload-btn">
                            Attach Files
                            <input type="file" multiple @change="uploadFile($event, f.key)" hidden />
                          </label>
                          <div class="bd-chips">
                            <span class="bd-chip-file" v-for="(fileId, i) in eF[f.key + '_attachments']" :key="i">
                              {{ fileId }} <span @click="removeFile(f.key, i)">&times;</span>
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div class="bd-f" style="margin-top: 24px;">
                    <label>Closing Petty Cash <span class="bd-f-hint">(carries to tomorrow)</span></label>
                    <div class="bd-pfx-wrap" style="max-width: 300px;">
                      <span class="bd-pfx">₹</span>
                      <input type="number" class="bd-input has-pfx" v-model.number="eF.day_end_petty_cash" min="0" />
                    </div>
                  </div>

                  <div class="bd-pay-bar">
                    <span class="bd-pay-lbl">Total Payments</span>
                    <span class="bd-pay-val">{{ inr(payTotal) }}</span>
                  </div>

                  <button class="bd-btn bd-btn-end" @click="doEndDay(activeEntry.name)" :disabled="busy">
                    <span v-if="busy"><span class="bd-btn-spin"></span> Saving...</span>
                    <span v-else>End Day &rarr;</span>
                  </button>
                </div>
              </template>
            </div>
          </template>

          <template v-if="historyEntries.length">
            <div class="bd-section-lbl" style="margin-top:28px;">Previous Entries</div>
            <div v-for="h in historyEntries" :key="h.name" class="bd-card c-done bd-content-card" @click="toggleHistory(h.date)">
              <div class="bd-hist-hd">
                <div class="bd-hist-left">
                  <span class="bd-hist-icon" style="display: flex; align-items: center; margin-right: 12px;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
                  </span>
                  <div>
                    <div class="bd-hist-date">{{ fullDate(h.date) }}</div>
                    <div class="bd-hist-meta">Ended {{ hhmm(h.day_ended_at) }}</div>
                  </div>
                </div>
                <div class="bd-hist-right">
                  <span class="bd-hist-total">{{ inr(entryCollections(h)) }}</span>
                  <span class="bd-chevron" :class="{ open: isHistOpen(h.date) }">▼</span>
                </div>
              </div>

              <div v-if="isHistOpen(h.date)" class="bd-hist-body" @click.stop>
                <div class="bd-hist-grid">
                  <div>
                    <div class="bd-hist-sec-title">Customer Count & Invoices</div>
                    <div class="bd-ro">
                      <div class="bd-ro-item" v-for="f in countFields" :key="f.key">
                        <div class="bd-ro-lbl">{{ f.label }}</div>
                        <div class="bd-ro-val">{{ h[f.key] || 0 }}</div>
                        <div class="bd-hist-rm" v-if="h[f.key + '_remarks']">{{ h[f.key + '_remarks'] }}</div>
                      </div>
                    </div>
                  </div>
                  <div>
                    <div class="bd-hist-sec-title">Payments</div>
                    <div class="bd-ro">
                      <div class="bd-ro-item" v-for="f in paymentFields" :key="f.key">
                        <div class="bd-ro-lbl">{{ f.label }}</div>
                        <div class="bd-ro-val">{{ inr(h[f.key]) }}</div>
                        <div class="bd-hist-rm" v-if="h[f.key + '_remarks']">{{ h[f.key + '_remarks'] }}</div>
                        <div class="bd-chips" v-if="h[f.key + '_attachments'] && h[f.key + '_attachments'].length">
                          <span class="bd-chip-file ro" v-for="id in h[f.key + '_attachments']" :key="id">{{ id }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>

        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue';

// ── Smart Field Configurations ────────────────────────────────────────────────
const countFields = [
  { key: 'walk_in', label: 'Walk In' },
  { key: 'new_customers', label: 'New Customers' },
  { key: 'existing_customers', label: 'Existing Customers' },
  { key: 'total_invoices', label: 'Total Invoices' }
];

const paymentFields = [
  { key: 'cc', label: 'Credit Card' },
  { key: 'bank_transfer', label: 'Bank Transfer' },
  { key: 'cash', label: 'Cash' },
  { key: 'other', label: 'Other' }
];

// ── Constants ─────────────────────────────────────────────────────────────────
const ENTRY_LIMIT = 12;
const API_BASE = 'aetas_customization.aetas_customization.doctype.boutique_day_entry.boutique_day_entry.';
const GET_CURRENT_BOUTIQUE = API_BASE + 'get_current_user_boutique';
const GET_ENTRIES    = API_BASE + 'get_entries_for_page';
const START_DAY      = API_BASE + 'start_day';
const END_DAY        = API_BASE + 'end_day';

// ── Props & State ─────────────────────────────────────────────────────────────
const props = defineProps({ page: { type: Object, default: null } });

const selectedBoutique = ref('');
const entries          = ref([]);
const loading          = ref(true);
const busy             = ref(false);
const openHistory      = ref([]);

const sF = reactive({ petty_cash: 0, remarks: '' });

// Dynamically initialize the End Form (eF) based on smart fields
const eF = reactive({ day_end_petty_cash: 0 });

// Counts: No attachments
countFields.forEach(f => {
  eF[f.key] = 0;
  eF[f.key + '_remarks'] = '';
});

// Payments: Includes attachments
paymentFields.forEach(f => {
  eF[f.key] = 0;
  eF[f.key + '_remarks'] = '';
  eF[f.key + '_attachments'] = [];
});

// ── Computed ──────────────────────────────────────────────────────────────────
const todayStr = computed(() => frappe.datetime.get_today());
const todayDisplay = computed(() => new Date(todayStr.value + 'T00:00:00').toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' }));
const todayDayName = computed(() => new Date(todayStr.value + 'T00:00:00').toLocaleDateString('en-IN', { weekday: 'long' }));

const prevEntry = computed(() => entries.value.find(e => e.date < todayStr.value && e.status !== 'Day Ended') || null);
const todayEntry = computed(() => entries.value.find(e => e.date === todayStr.value) || null);
const activeEntry = computed(() => prevEntry.value || todayEntry.value);

const pendingAction = computed(() => {
  if (prevEntry.value) return 'end_previous';
  if (!todayEntry.value || todayEntry.value.status === 'Draft') return 'start_today';
  if (todayEntry.value.status === 'Day Started') return 'end_today';
  return 'all_done';
});

const payTotal = computed(() => paymentFields.reduce((sum, f) => sum + (eF[f.key] || 0), 0));

// Card UI Modifiers
const todayCardCls = computed(() => {
  if (prevEntry.value) return 'c-locked';
  if (pendingAction.value.includes('start') || pendingAction.value.includes('end')) return 'c-active';
  return '';
});

const todayHdCls = computed(() => {
  if (prevEntry.value) return 'bg-red';
  if (pendingAction.value === 'start_today') return 'bg-indigo';
  if (pendingAction.value === 'end_today') return 'bg-amber';
  return 'bg-green';
});

const todayChipCls = computed(() => {
  if (prevEntry.value) return 'red';
  if (pendingAction.value === 'start_today') return 'indigo';
  if (pendingAction.value === 'end_today') return 'amber';
  return 'green';
});

const todayChipLabel = computed(() => {
  if (prevEntry.value) return 'Pending Action';
  if (pendingAction.value === 'start_today') return 'Not Started';
  if (pendingAction.value === 'end_today') return 'In Progress';
  return 'Complete';
});

const shiftDuration = (start, end) => {
  if (!start || !end) return '—';
  const s = new Date(start.replace(' ', 'T'));
  const e = new Date(end.replace(' ', 'T'));
  const diffMs = e - s;
  if (isNaN(diffMs)) return '—';
  const diffHrs = Math.floor(diffMs / 3600000);
  const diffMins = Math.floor((diffMs % 3600000) / 60000);
  return `${diffHrs}h ${diffMins}m`;
};

const timeline = computed(() =>
  Array.from({ length: 7 }, (_, i) => {
    const d = frappe.datetime.add_days(todayStr.value, i - 6);
    const entry = entries.value.find(e => e.date === d);
    const st = entry ? entry.status : 'None';
    let badge, cls;
    if (st === 'Day Ended') { badge = 'Done'; cls = 's-done'; }
    else if (st === 'Day Started') { badge = 'Started'; cls = 's-started'; }
    else if (d > todayStr.value) { badge = 'Future'; cls = 's-future'; }
    else { badge = 'Missing'; cls = 's-missing'; }
    return { date: d, isToday: (d === todayStr.value), short: new Date(d + 'T00:00:00').toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }), badge, cls };
  })
);

const historyEntries = computed(() => entries.value.filter(e => e.status === 'Day Ended' && e.date !== todayStr.value).slice(0, 7));

// ── API helper ────────────────────────────────────────────────────────────────
const call = (method, args = {}) => new Promise((resolve, reject) => frappe.call({ method, args, callback: r => resolve(r?.message), error: reject }));

// ── Data & Upload Logic ───────────────────────────────────────────────────────
const refresh = async () => {
  if (!selectedBoutique.value) return;
  loading.value = true;
  try {
    entries.value = await call(GET_ENTRIES, { boutique: selectedBoutique.value, limit: ENTRY_LIMIT }) || [];
    prefillStartCash();
  } catch (err) {
    frappe.msgprint('Could not load entries');
  } finally {
    loading.value = false;
  }
};

const prefillStartCash = () => {
  if (!todayEntry.value) {
    const last = entries.value.find(e => e.status === 'Day Ended');
    if (last) sF.petty_cash = last.day_end_petty_cash || 0;
  }
  Object.keys(eF).forEach(k => { if(typeof eF[k] === 'number') eF[k] = 0; else if(Array.isArray(eF[k])) eF[k] = []; else eF[k] = ''; });
};

const uploadFile = async (event, metricKey) => {
  const files = event.target.files;
  if (!files.length) return;
  
  for (let file of files) {
    const formData = new FormData();
    formData.append('file', file, file.name);
    formData.append('is_private', 0);

    try {
      const res = await fetch('/api/method/upload_file', {
        method: 'POST',
        headers: { 'X-Frappe-CSRF-Token': frappe.csrf_token },
        body: formData
      });
      const data = await res.json();
      if (data.message && data.message.name) {
        eF[metricKey + '_attachments'].push(data.message.name);
      }
    } catch (err) {
      console.error(err);
      frappe.msgprint('File upload failed');
    }
  }
  event.target.value = ''; 
};

const removeFile = (metricKey, idx) => { eF[metricKey + '_attachments'].splice(idx, 1); };

// ── Actions ───────────────────────────────────────────────────────────────────
const doStartDay = async () => {
  busy.value = true;
  try {
    await call(START_DAY, { boutique: selectedBoutique.value, petty_cash: sF.petty_cash, remarks: sF.remarks });
    frappe.show_alert({ message: 'Day started successfully.', indicator: 'green' });
    await refresh();
  } catch (err) {
    frappe.msgprint({ title: 'Error', message: err.message, indicator: 'red' });
  } finally {
    busy.value = false;
  }
};

const doEndDay = async (entryName) => {
  busy.value = true;
  try {
    const res = await call(END_DAY, { entry_name: entryName, payload: JSON.stringify(eF) });
    frappe.show_alert({ message: 'Day ended successfully.', indicator: 'green' });
    await refresh();
  } catch (err) {
    frappe.msgprint({ title: 'Error', message: err.message, indicator: 'red' });
  } finally {
    busy.value = false;
  }
};

// ── Formatters & Utilities ────────────────────────────────────────────────────
const toggleHistory = (date) => { const i = openHistory.value.indexOf(date); if (i > -1) openHistory.value.splice(i, 1); else openHistory.value.push(date); };
const isHistOpen = (date) => openHistory.value.includes(date);

const inr = (val) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(val || 0);
const hhmm = (dt) => {
  if (!dt) return '—';
  const parts = String(dt).split(' ');
  if (parts.length < 2) return '—';
  const hh = parseInt(parts[1].split(':')[0]), mm = parts[1].split(':')[1];
  return `${hh % 12 || 12}:${mm} ${hh >= 12 ? 'PM' : 'AM'}`;
};
const fullDate = (date) => date ? new Date(date + 'T00:00:00').toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }) : '';
const entryCollections = (e) => e ? (e.cc || 0) + (e.bank_transfer || 0) + (e.cash || 0) + (e.other || 0) : 0;

// ── Lifecycle ─────────────────────────────────────────────────────────────────
onMounted(async () => {
  if (props.page) {
    props.page.set_primary_action(__('Refresh'), refresh, 'refresh');
  }
  
  try {
    const boutique = await call(GET_CURRENT_BOUTIQUE);
    if (boutique) {
      selectedBoutique.value = boutique;
      await refresh();
    } else {
      loading.value = false;
    }
  } catch { loading.value = false; }
});
</script>

<style scoped>
/* ── Base ── */
.bd-page { display: flex; flex-direction: column; min-height: calc(100vh - 120px); background: #f4f7f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #334155; }
.bd-container { max-width: 900px; width: 100%; margin: 0 auto; padding: 24px 16px 60px; display: flex; flex-direction: column; gap: 20px; }
.bd-card { background: #ffffff; border-radius: 16px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; overflow: hidden; }
.bd-header-card { padding: 24px 28px; }
.bd-header-inner { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.bd-eyebrow { display: flex; align-items: center; gap: 8px; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: #64748b; margin-bottom: 6px; }
.bd-eyebrow-pip { width: 8px; height: 8px; border-radius: 50%; background: #6366f1; flex-shrink: 0; }
.bd-title { font-size: 2rem; font-weight: 800; color: #0f172a; line-height: 1.2; }
.bd-boutique-pill { display: inline-flex; align-items: center; gap: 6px; margin-top: 10px; padding: 6px 14px; background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 20px; font-size: 0.85rem; font-weight: 600; color: #475569; }
.bd-date-box { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 14px 20px; text-align: right; }
.bd-date-day { font-size: 0.7rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: #64748b; margin-bottom: 4px; }
.bd-date-val { font-size: 1.15rem; font-weight: 700; color: #0f172a; }

.bd-tl-card { padding: 16px 0; overflow-x: auto; }
.bd-tl-inner { display: flex; gap: 0; padding: 0 16px; min-width: max-content; position: relative; align-items: stretch; }
.bd-tl-inner::before { content: ''; position: absolute; top: 26px; left: 56px; right: 56px; height: 2px; background: #e2e8f0; z-index: 0; }
.bd-tl-pill { display: flex; flex-direction: column; align-items: center; padding: 14px 16px; min-width: 90px; position: relative; flex: 1; border-radius: 12px; }
.bd-tl-pill.is-today { background: #e0e7ff; }
.bd-tl-status-dot { width: 22px; height: 22px; border-radius: 50%; flex-shrink: 0; margin-bottom: 8px; position: relative; z-index: 1; background: #ffffff; border: 3px solid #cbd5e1; }
.bd-tl-status-dot.s-done { border-color: #10b981; background: #10b981; }
.bd-tl-status-dot.s-started { border-color: #f59e0b; background: #f59e0b; }
.bd-tl-status-dot.s-missing { border-color: #ef4444; background: #ef4444; }
.bd-tl-status-dot.s-future { border-color: #e2e8f0; background: #f8fafc; }
.bd-tl-pill.is-today .bd-tl-status-dot { border-color: #6366f1; background: #6366f1; box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.2); }
.bd-tl-date { font-size: 0.75rem; font-weight: 700; color: #64748b; }
.bd-tl-badge { font-size: 0.65rem; font-weight: 700; color: #94a3b8; margin-top: 4px; text-transform: uppercase; }

/* Dynamic Card Content */
.bd-body { display: flex; flex-direction: column; gap: 20px; }
.bd-section-lbl { font-size: 0.75rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: #475569; display: flex; align-items: center; gap: 8px; }
.bd-content-card { border-left: 6px solid transparent; }
.bd-content-card.c-active { border-left-color: #6366f1; }
.bd-content-card.c-done { border-left-color: #10b981; cursor: pointer; }
.bd-card-hd { padding: 18px 24px; display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 1px solid #f1f5f9; }
.bd-card-hd.bg-red { background: #fef2f2; }
.bd-card-hd.bg-indigo { background: #eef2ff; }
.bd-card-hd.bg-amber { background: #fffbeb; }
.bd-card-hd.bg-green { background: #f0fdf4; }
.bd-card-eyebrow { font-size: 0.7rem; font-weight: 700; text-transform: uppercase; color: #64748b; margin-bottom: 6px; }
.bd-card-date { font-size: 1.15rem; font-weight: 800; color: #0f172a; }
.bd-chip { padding: 6px 14px; border-radius: 24px; font-size: 0.75rem; font-weight: 700; }
.bd-chip.red { background: #fee2e2; color: #b91c1c; }
.bd-chip.indigo { background: #e0e7ff; color: #4338ca; }
.bd-chip.amber { background: #fef3c7; color: #b45309; }
.bd-chip.green { background: #dcfce7; color: #15803d; }
.bd-inner { padding: 24px; }
.bd-inner.bg-faint { background: #f8fafc; border-bottom: 1px solid #f1f5f9; }
.bd-inner-hd { display: flex; align-items: center; gap: 10px; margin-bottom: 18px; }
.bd-inner-icon { font-size: 1.25rem; }
.bd-inner-title { font-size: 1rem; font-weight: 700; color: #0f172a; flex: 1; }
.bd-done-badge { background: #dcfce7; color: #15803d; font-size: 0.7rem; font-weight: 700; padding: 2px 8px; border-radius: 12px; margin-left: auto; text-transform: uppercase; letter-spacing: 0.05em; }

/* Grid and Smart Blocks */
.bd-fg-title { font-size: 0.75rem; font-weight: 700; text-transform: uppercase; color: #475569; margin: 12px 0; border-bottom: 1px solid #f1f5f9; padding-bottom: 8px; }
.bd-grid { display: grid; gap: 16px; margin-bottom: 24px; }
.bd-g2 { grid-template-columns: repeat(2, 1fr); }

.bd-metric-block { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px; }
.bd-metric-top { display: flex; flex-direction: column; margin-bottom: 8px; }
.bd-metric-top label { font-size: 0.8rem; font-weight: 700; color: #334155; margin-bottom: 6px; }
.bd-metric-tools { display: flex; flex-direction: column; gap: 8px; border-top: 1px dashed #cbd5e1; padding-top: 8px; }

.bd-input, .bd-ta { width: 100%; padding: 10px 14px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 0.9rem; color: #0f172a; background: #ffffff; box-sizing: border-box; }
.bd-input-sm { padding: 6px 10px; font-size: 0.85rem; background: #f1f5f9; }
.bd-input:focus { outline: none; border-color: #6366f1; box-shadow: 0 0 0 3px rgba(99,102,241,0.15); }

/* File Uploader UI */
.bd-upload-wrap { display: flex; flex-direction: column; gap: 6px; }
.bd-upload-btn { display: inline-block; padding: 4px 10px; background: #e2e8f0; color: #475569; border-radius: 6px; font-size: 0.75rem; font-weight: 700; cursor: pointer; align-self: flex-start; transition: background 0.2s; }
.bd-upload-btn:hover { background: #cbd5e1; }
.bd-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.bd-chip-file { background: #e0e7ff; color: #4338ca; padding: 2px 8px; border-radius: 12px; font-size: 0.7rem; font-weight: 600; display: flex; align-items: center; gap: 6px; }
.bd-chip-file span { cursor: pointer; font-size: 0.9rem; font-weight: 800; opacity: 0.6; }
.bd-chip-file span:hover { opacity: 1; color: #b91c1c; }
.bd-chip-file.ro { background: #f1f5f9; color: #475569; padding: 4px 10px; }

/* History Details */
.bd-hist-hd { display: flex; justify-content: space-between; align-items: center; padding: 20px 24px; cursor: pointer; }
.bd-hist-left { display: flex; align-items: center; }
.bd-hist-date { font-weight: 800; color: #0f172a; font-size: 1.05rem; margin-bottom: 2px; }
.bd-hist-meta { font-size: 0.75rem; color: #64748b; font-weight: 600; }
.bd-hist-right { display: flex; align-items: center; gap: 16px; }
.bd-hist-total { font-size: 1.1rem; font-weight: 800; color: #10b981; }
.bd-chevron { color: #94a3b8; font-size: 0.85rem; transition: transform 0.2s; display: inline-block; }
.bd-chevron.open { transform: rotate(180deg); color: #0f172a; }

.bd-hist-body { padding: 0 24px 24px; border-top: 1px solid #f1f5f9; }
.bd-hist-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 24px; padding-top: 20px; }
.bd-hist-sec-title { font-size: 0.75rem; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 12px; }
.bd-hist-rm { font-size: 0.8rem; color: #64748b; font-style: italic; margin-top: 4px; }

.bd-ro { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 16px; }
.bd-ro-lbl { font-size: 0.7rem; font-weight: 700; text-transform: uppercase; color: #64748b; margin-bottom: 4px; }
.bd-ro-val { font-size: 0.95rem; font-weight: 700; color: #0f172a; }
.bd-ro-val.accent { color: #6366f1; }

.bd-pfx-wrap { display: flex; }
.bd-pfx { display: flex; align-items: center; padding: 0 14px; background: #f8fafc; border: 1px solid #cbd5e1; border-right: none; border-radius: 8px 0 0 8px; font-size: 0.9rem; font-weight: 600; color: #64748b; }
.bd-input.has-pfx { border-radius: 0 8px 8px 0; }

.bd-pay-bar { display: flex; justify-content: space-between; align-items: center; background: #f8fafc; padding: 16px 20px; border-radius: 12px; border: 1px solid #e2e8f0; margin-top: 32px; }
.bd-pay-lbl { font-size: 0.9rem; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: 0.05em; }
.bd-pay-val { font-size: 1.5rem; font-weight: 800; color: #10b981; }

.bd-btn { width: 100%; padding: 14px; border: none; border-radius: 10px; font-size: 1rem; font-weight: 700; cursor: pointer; margin-top: 24px; display: flex; align-items: center; justify-content: center; gap: 10px; }
.bd-btn-start { background: #6366f1; color: #ffffff; }
.bd-btn-end { background: #f59e0b; color: #ffffff; }
.bd-btn:disabled { opacity: 0.7; cursor: not-allowed; }
.bd-btn-spin { width: 16px; height: 16px; border: 3px solid rgba(255,255,255,0.3); border-top-color: #fff; border-radius: 50%; animation: spin 1s linear infinite; }

@media (max-width: 640px) {
  .bd-g2 { grid-template-columns: 1fr; }
  .bd-header-inner { flex-direction: column; }
  .bd-date-box { text-align: left; width: 100%; }
}

/* Empty States */
.bd-loading { text-align: center; padding: 60px 20px; }
.bd-spinner { width: 48px; height: 48px; border: 4px solid #f1f5f9; border-top-color: #6366f1; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 16px; }
.bd-loading-txt { color: #64748b; font-size: 0.95rem; font-weight: 600; }
.bd-empty { text-align: center; padding: 80px 20px; }
.bd-empty-icon { margin-bottom: 16px; }
.bd-empty-title { font-size: 1.25rem; font-weight: 700; color: #0f172a; }
.bd-empty-sub { font-size: 0.95rem; color: #64748b; margin-top: 8px; line-height: 1.5; }

/* All Good State */
.bd-allgood { text-align: center; padding: 48px 24px 32px; }
.bd-allgood-icon  { margin-bottom: 16px; animation: pop 0.6s cubic-bezier(0.175, 0.885, 0.32, 1.275); display: flex; justify-content: center; }
.bd-allgood-title { font-size: 1.5rem; font-weight: 800; color: #0f172a; }
.bd-allgood-sub   { color: #64748b; margin-top: 8px; font-size: 0.95rem; }

.bd-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 16px;
  margin-top: 32px;
}
.bd-stat {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 20px 16px;
  text-align: center;
}
.bd-stat-val   { font-size: 1.5rem; font-weight: 800; color: #0f172a; }
.bd-stat-val.g { color: #10b981; }
.bd-stat-val.p { color: #6366f1; }
.bd-stat-lbl   { font-size: 0.7rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 6px; }

/* Micro-Stats styling */
.bd-stat-micro {
  font-size: 0.7rem;
  font-weight: 600;
  color: #94a3b8;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #e2e8f0;
  display: flex;
  justify-content: center;
  gap: 4px;
}
.color-indigo { color: #6366f1; }
.color-red { color: #ef4444; font-weight: 700; }

@keyframes spin { to { transform: rotate(360deg); } }
@keyframes pop { 0% { transform: scale(0.8); } 70% { transform: scale(1.1); } 100% { transform: scale(1); } }
</style>