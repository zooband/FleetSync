import { createApp } from 'vue'

import App from './App.vue'
import router from './router'

import 'primeicons/primeicons.css'
import '@/assets/main.css'

import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'
import ToastService from 'primevue/toastservice'
import ConfirmationService from 'primevue/confirmationservice'

const app = createApp(App)
app.use(PrimeVue, {
    theme: {
        preset: Aura,
        options: {
            prefix: 'p',
            darkModeSelector: 'system',
            cssLayer: false,
        },
    },
})
app.use(router)
app.use(ToastService)
app.use(ConfirmationService)

app.mount('#app')
