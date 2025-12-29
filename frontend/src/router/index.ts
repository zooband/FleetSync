import { createRouter, createWebHashHistory } from 'vue-router'
import { auth, getHomePath, getMyFleetPath, getMyInfoPath, isLoggedIn } from '@/services/auth'

const routes = [
    {
        path: '/',
        redirect: () => getHomePath(),
    },
    {
        path: '/login',
        name: 'Login',
        component: () => import('@/views/Login.vue'),
        meta: { title: '登录', showInMenu: false, public: true, layout: 'blank' },
    },
    {
        path: '/my',
        name: 'MyInfo',
        redirect: () => getMyInfoPath(),
        meta: { title: '我的信息', showInMenu: false },
    },
    {
        path: '/my-fleet',
        name: 'MyFleet',
        redirect: () => getMyFleetPath(),
        meta: { title: '我的车队', showInMenu: false },
    },
    {
        path: '/distribution',
        name: 'DistributionCenter',
        component: () => import('@/views/DistributionCenter.vue'),
        meta: { title: '配送中心', showInMenu: true, order: 0, roles: ['admin'] },
    },
    {
        path: '/personnels/:personId(\\d+)',
        name: 'PersonnelInfo',
        component: () => import('@/views/PersonnelInfo.vue'),
        meta: { title: '人员详情', showInMenu: false },
    },
    {
        path: '/distribution/:centerId(\\d+)',
        name: 'DistributionInfo',
        component: () => import('@/views/DistributionInfo.vue'),
        meta: { title: '配送中心详情', showInMenu: false, roles: ['admin'] },
    },
    {
        path: '/fleet/:fleetId(\\d+)',
        name: 'FleetInfo',
        component: () => import('@/views/FleetInfo.vue'),
        meta: { title: '车队详情', showInMenu: false },
    },
    {
        path: '/order',
        name: 'OrderManagement',
        component: () => import('@/views/OrderManagement.vue'),
        meta: { title: '运单管理', showInMenu: true, order: 4, roles: ['admin', 'manager'] },
    },
    {
        path: '/incident',
        name: 'IncidentList',
        component: () => import('@/views/IncidentList.vue'),
        meta: { title: '异常事件', showInMenu: true, order: 5, roles: ['admin', 'manager'] },
    },
]

const router = createRouter({
    history: createWebHashHistory(),
    routes,
})

router.beforeEach((to) => {
    const isPublic = (to.meta as Record<string, unknown>)?.public === true
    if (isPublic) return true

    if (!isLoggedIn.value) {
        return { path: '/login', query: { redirect: to.fullPath } }
    }

    const role = auth.value?.role
    if (!role) return { path: '/login' }

    // 基于 meta.roles 的粗粒度控制（主要用于 admin 页面）
    const allowedRoles = (to.meta as Record<string, unknown>)?.roles as string[] | undefined
    if (Array.isArray(allowedRoles) && allowedRoles.length > 0 && !allowedRoles.includes(role)) {
        return getHomePath()
    }

    // 细粒度：司机只能访问自己的 PersonnelInfo
    if (role === 'staff') {
        if (to.name === 'PersonnelInfo') {
            const pid = Number((to.params as Record<string, unknown>)?.personId)
            if (Number.isFinite(pid) && auth.value?.personnelId === pid) return true
            return getHomePath()
        }
        if (to.name === 'MyInfo' || to.name === 'Login') return true
        return getHomePath()
    }

    // 主管：可访问自己的车队与自己的信息 + 运单管理
    if (role === 'manager') {
        if (to.name === 'FleetInfo') {
            const fid = Number((to.params as Record<string, unknown>)?.fleetId)
            if (Number.isFinite(fid) && auth.value?.fleetId === fid) return true
            return getHomePath()
        }
        // 主管需要查询司机绩效追踪：允许访问人员详情页（具体可见范围由后端鉴权兜底）
        if (to.name === 'PersonnelInfo') return true
        if (
            to.name === 'OrderManagement' ||
            to.name === 'IncidentList' ||
            to.name === 'MyInfo' ||
            to.name === 'MyFleet'
        )
            return true
        return getHomePath()
    }

    // admin 放行
    return true
})

export default router
