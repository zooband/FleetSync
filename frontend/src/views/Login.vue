<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import InputText from 'primevue/inputtext'
import PrimeButton from 'primevue/button'
import { apiJson } from '@/services/api'
import { setAuth, getHomePath } from '@/services/auth'

defineOptions({ name: 'LoginPage' })

type LoginResponse = {
    token: string
    role: 'admin' | 'manager' | 'staff'
    personnel_id?: number | null
    fleet_id?: number | null
    display_name?: string | null
}

const router = useRouter()
const route = useRoute()

const username = ref('')
const submitting = ref(false)
const errorText = ref('')

async function doLogin() {
    errorText.value = ''
    const u = username.value.trim()
    if (!u) {
        errorText.value = '请输入用户名（admin 或 工号）'
        return
    }

    submitting.value = true
    try {
        const data = await apiJson<LoginResponse>('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: u }),
        }, { auth: false })

        setAuth({
            token: data.token,
            role: data.role,
            personnelId: data.personnel_id ?? undefined,
            fleetId: data.fleet_id ?? undefined,
            displayName: data.display_name ?? undefined,
        })

        const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : ''
        await router.replace(redirect || getHomePath())
    } catch (e) {
        errorText.value = (e as Error).message || '登录失败'
    } finally {
        submitting.value = false
    }
}
</script>

<template>
    <div class="min-h-[calc(100vh-3rem)] flex items-center justify-center">
        <div class="w-full max-w-md p-6 rounded border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
            <h1 class="text-xl font-bold mb-4">登录</h1>
            <div class="space-y-3">
                <div class="flex flex-col gap-2">
                    <label class="text-sm text-gray-600 dark:text-gray-300">用户名</label>
                    <InputText v-model="username" placeholder="admin 或 工号" @keydown.enter="doLogin" />
                </div>

                <div v-if="errorText" class="text-sm text-red-600">{{ errorText }}</div>

                <PrimeButton label="登录" class="w-full" :loading="submitting" @click="doLogin" />
            </div>
        </div>
    </div>
</template>
