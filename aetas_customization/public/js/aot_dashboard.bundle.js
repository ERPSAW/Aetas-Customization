import { createApp } from 'vue';
import AotDashboard from './AotDashboard.vue';

class AotDashboardUI {
    constructor({ wrapper, page }) {
        this.wrapper = wrapper;
        this.page = page;
        this.app = null;
        this.init();
    }

    init() {
        this.app = createApp(AotDashboard, { page: this.page });
        this.app.mount(this.wrapper);
    }

    destroy() {
        if (this.app) {
            this.app.unmount();
            this.app = null;
        }
    }
}

frappe.provide('aot.dashboard');
aot.dashboard.AotDashboardUI = AotDashboardUI;

export default AotDashboardUI;
