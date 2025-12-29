<template>
    <div class="app-layout flex min-h-screen">
        <!-- 抽屉式侧边栏（登录页隐藏） -->
        <aside v-if="!isBlankLayout"
            class="w-72 h-screen bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 p-6 shrink-0 flex flex-col overflow-hidden">
            <h2 class="text-xl font-bold mb-6">物流调度系统</h2>
            <div class="flex-1 overflow-auto">
                <PanelMenu :model="panelModel" class="w-full" />
            </div>

            <PrimeButton class="mt-4 w-full" label="退出登录" severity="secondary" @click="logout" />
        </aside>
        <!-- 主内容区 -->
        <main class="flex-1 h-screen p-6 overflow-auto bg-white dark:bg-gray-950">
            <router-view />
        </main>
    </div>
</template>

<script lang="ts">
import { defineComponent, computed, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import PanelMenu from 'primevue/panelmenu'
import PrimeButton from 'primevue/button'
import { auth, clearAuth, getHomePath, getMyFleetPath, getMyInfoPath } from '@/services/auth'

export default defineComponent({
    name: 'LayoutPage',
    components: {
        PanelMenu,
        PrimeButton,
    },
    setup() {
        const router = useRouter()
        const route = useRoute()
        const sidebarVisible = ref(false)

        const isBlankLayout = computed(() => (route.meta as Record<string, unknown>)?.layout === 'blank')

        const role = computed(() => auth.value?.role ?? 'staff')

        const menu = computed(() => {
            if (role.value === 'admin') {
                return router
                    .getRoutes()
                    .filter(r => r.meta?.showInMenu)
                    .sort((a, b) => (Number(a.meta?.order) || 0) - (Number(b.meta?.order) || 0))
                    .map(r => ({
                        path: r.path,
                        title: r.meta?.title as string,
                    }))
            }

            if (role.value === 'manager') {
                return [
                    { path: '/my-fleet', title: '我的车队' },
                    { path: '/order', title: '运单管理' },
                    { path: '/incident', title: '异常事件' },
                    { path: '/my', title: '我的信息' },
                ]
            }

            // 司机/普通员工
            return [{ path: '/my', title: '我的信息' }]
        })

        const panelModel = computed(() =>
            menu.value.map((m) => ({
                label: m.title,
                command: () => {
                    sidebarVisible.value = false
                    router.push(m.path)
                },
            }))
        )

        function logout() {
            clearAuth()
            sidebarVisible.value = false
            router.replace('/login')
        }

        return { panelModel, sidebarVisible, logout, isBlankLayout, getHomePath, getMyFleetPath, getMyInfoPath }
    }
})
</script>