import { createApp } from 'vue';
import DayEntry from './DayEntry.vue';

class DayEntryUI {
    constructor({ wrapper, page }) {
        this.$wrapper = $(wrapper);
        this.page = page;
        this.app = null;
        this.init();
    }

    init() {
        // Mount Vue app
        this.app = createApp(DayEntry, {
            page: this.page
        });
        this.app.mount(this.$wrapper.get(0));
    }

    destroy() {
        if (this.app) {
            this.app.unmount();
            this.app = null;
        }
    }
}

// Expose to global namespace
frappe.provide("dayentry.ui");
dayentry.ui.DayEntryUI = DayEntryUI;

export default DayEntryUI;