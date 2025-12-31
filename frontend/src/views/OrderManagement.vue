<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import PrimeButton from 'primevue/button'
import PrimeDialog from 'primevue/dialog'
import AutoComplete from 'primevue/autocomplete'
import { useToast } from 'primevue/usetoast'
import EntityCardBoard from '@/components/EntityCardBoard.vue'
import type { Columns, Order, Vehicle } from '@/types'
import { OrderColumns } from '@/types'
import { apiFetch, apiJson } from '@/services/api'

const toast = useToast()

// 状态变量
const pendingOrders = ref<Order[]>([])
const pendingTotal = ref(0)

const loadingOrders = ref<Order[]>([])
const loadingTotal = ref(0)

const transitOrders = ref<Order[]>([])
const transitTotal = ref(0)

const doneOrders = ref<Order[]>([])
const doneTotal = ref(0)

const cancelledOrders = ref<Order[]>([])
const cancelledTotal = ref(0)

const activeTab = ref<'pending' | 'loading' | 'transit' | 'done' | 'cancelled'>('pending')
const mounted = reactive({ pending: true, loading: false, transit: false, done: false, cancelled: false })
watch(activeTab, (v) => {
    mounted[v] = true
})

const refreshKey = reactive({ pending: 0, loading: 0, transit: 0, done: 0, cancelled: 0 })

function showError(message: string) {
    toast.add({ severity: 'error', summary: '错误', detail: message })
}

function showSuccess(message: string) {
    toast.add({ severity: 'success', summary: '成功', detail: message, life: 1500 })
}

function buildParams(query: string, limit: number, offset: number, extra?: Record<string, string>) {
    const params = new URLSearchParams({ q: query, limit: String(limit), offset: String(offset) })
    if (extra) {
        for (const [k, v] of Object.entries(extra)) params.set(k, v)
    }
    return params
}

type PaginatedResponse<T> = { data: T[]; total: number }

async function searchPendingOrders(query: string, limit: number, offset: number) {
    const params = buildParams(query, limit, offset)
    const data = await apiJson<PaginatedResponse<Order>>(`/api/orders/pending?${params}`)
    pendingOrders.value = data.data ?? []
    pendingTotal.value = data.total ?? pendingOrders.value.length
}

async function searchLoadingOrders(query: string, limit: number, offset: number) {
    const params = buildParams(query, limit, offset)
    const data = await apiJson<PaginatedResponse<Order>>(`/api/orders/loading?${params}`)
    loadingOrders.value = data.data ?? []
    loadingTotal.value = data.total ?? loadingOrders.value.length
}

async function searchTransitOrders(query: string, limit: number, offset: number) {
    const params = buildParams(query, limit, offset)
    const data = await apiJson<PaginatedResponse<Order>>(`/api/orders/transit?${params}`)
    transitOrders.value = data.data ?? []
    transitTotal.value = data.total ?? transitOrders.value.length
}

async function searchDoneOrders(query: string, limit: number, offset: number) {
    const params = buildParams(query, limit, offset)
    const data = await apiJson<PaginatedResponse<Order>>(`/api/orders/done?${params}`)
    doneOrders.value = data.data ?? []
    doneTotal.value = data.total ?? doneOrders.value.length
}

async function searchCancelledOrders(query: string, limit: number, offset: number) {
    const params = buildParams(query, limit, offset)
    const data = await apiJson<PaginatedResponse<Order>>(`/api/orders/cancelled?${params}`)
    cancelledOrders.value = data.data ?? []
    cancelledTotal.value = data.total ?? cancelledOrders.value.length
}

async function createOrder(order: Partial<Order>) {
    // 订单一经创建不可编辑：默认直接创建为“待处理”
    const payload: Partial<Order> = {
        ...order,
        status: '待处理',
        vehicle_id: null,
    }

    const res = await apiFetch('/api/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    })
    if (!res.ok) throw new Error('添加订单失败')
}

async function cancelOrder(orderId: number) {
    const res = await apiFetch(`/api/orders/${orderId}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: '已取消' }),
    })
    if (!res.ok) throw new Error('取消订单失败')
}

async function assignVehicle(orderId: number, vehicleId: string) {
    const res = await apiFetch(`/api/orders/${orderId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vehicle_id: vehicleId }),
    })
    if (!res.ok) {
        let msg = '转为装货中失败'
        try {
            const raw = (await res.json()) as { detail?: string }
            if (raw?.detail) msg = raw.detail
        } catch {
            try {
                const t = await res.text()
                if (t) msg = t
            } catch {
                // ignore
            }
        }
        throw new Error(msg)
    }
}

// 待处理 -> 运输中：分配车辆弹窗
const assignVisible = ref(false)
const assigningOrder = ref<Order | null>(null)
const vehicleSuggestions = ref<Vehicle[]>([])
const selectedVehicle = ref<Vehicle | string | null>(null)
const assigning = ref(false)

function openAssignVehicle(order: Order) {
    assigningOrder.value = order
    selectedVehicle.value = null
    vehicleSuggestions.value = []
    assignVisible.value = true

    // PrimeVue AutoComplete 在某些场景下不会触发 complete（比如首次打开/空输入）。
    // 这里主动拉一次，确保会产生 /api/vehicles 请求并显示候选。
    void completeVehicle('')
}

async function completeVehicle(query: string | undefined) {
    try {
        const q = (query ?? '').trim()
        // 空闲或者装货中的车辆
        const params = new URLSearchParams({ q, limit: '10', offset: '0', status: '空闲,装货中' })
        const raw = await apiJson<unknown>(`/api/vehicles?${params}`)
        const rows = Array.isArray(raw) ? (raw as Vehicle[]) : (((raw as { data?: Vehicle[] })?.data ?? raw) as Vehicle[])

        const order = assigningOrder.value
        const needW = order ? Number((order as unknown as Record<string, unknown>)['weight']) : NaN
        const needV = order ? Number((order as unknown as Record<string, unknown>)['volume']) : NaN

        vehicleSuggestions.value = (rows ?? []).filter(v => {
            const rec = v as unknown as Record<string, unknown>
            const status = String(rec['vehicle_status'] ?? '')
            if (status !== '空闲' && status !== '装货中') return false

            // 后端返回 VehicleView 时会带 remaining_*；如果没带就不做容量过滤。
            const remW = Number(rec['remaining_weight'])
            const remV = Number(rec['remaining_volume'])
            const hasRemW = Number.isFinite(remW)
            const hasRemV = Number.isFinite(remV)
            const hasNeedW = Number.isFinite(needW)
            const hasNeedV = Number.isFinite(needV)

            if (hasNeedW && hasRemW && remW < needW) return false
            if (hasNeedV && hasRemV && remV < needV) return false

            return true
        })
    } catch (e) {
        showError((e as Error).message || '获取车辆列表失败')
        vehicleSuggestions.value = []
    }
}

function getVehicleId(v: Vehicle | string | null): string | null {
    if (v == null) return null
    if (typeof v === 'string') return v
    const raw = (v as unknown as Record<string, unknown>)['vehicle_id']
    return raw == null ? null : String(raw)
}

async function confirmAssignVehicle() {
    const order = assigningOrder.value
    if (!order) return
    const vehicleId = getVehicleId(selectedVehicle.value)
    if (!vehicleId) {
        showError('请选择车牌号')
        return
    }

    assigning.value = true
    try {
        await assignVehicle(order.order_id as unknown as number, vehicleId)
        assignVisible.value = false
        assigningOrder.value = null
        showSuccess('已转为装货中')
        refreshKey.pending++
        refreshKey.loading++
        activeTab.value = 'loading'
    } catch (e) {
        const msg = (e as Error).message || '操作失败'
        // Readme 要求：超载/容量不足要提示“超出最大载重”
        if (msg.includes('容量不足') || msg.includes('载重') || msg.includes('超出')) {
            showError('超出最大载重')
        } else {
            showError(msg)
        }
    } finally {
        assigning.value = false
    }
}

async function onCancelOrder(order: Order) {
    try {
        await cancelOrder(order.order_id as unknown as number)
        showSuccess('已取消订单')
        refreshKey.pending++
        refreshKey.loading++
        refreshKey.transit++
        refreshKey.done++
        refreshKey.cancelled++
    } catch (e) {
        showError((e as Error).message || '操作失败')
    }
}

const pendingOps = {
    get data() {
        return pendingOrders.value
    },
    get total() {
        return pendingTotal.value
    },
    search: searchPendingOrders,
    create: createOrder,
}

const loadingOps = {
    get data() {
        return loadingOrders.value
    },
    get total() {
        return loadingTotal.value
    },
    search: searchLoadingOrders,
}

const transitOps = {
    get data() {
        return transitOrders.value
    },
    get total() {
        return transitTotal.value
    },
    search: searchTransitOrders,
}

const doneOps = {
    get data() {
        return doneOrders.value
    },
    get total() {
        return doneTotal.value
    },
    search: searchDoneOrders,
}

const cancelledOps = {
    get data() {
        return cancelledOrders.value
    },
    get total() {
        return cancelledTotal.value
    },
    search: searchCancelledOrders,
}

const pendingCreateColumns: readonly Columns[] = OrderColumns.filter(c =>
    ['origin', 'destination', 'weight', 'volume'].includes(c.key)
)

</script>

<template>
    <div class="p-6">
        <h2 class="text-xl font-bold mb-4">订单管理</h2>

        <Tabs v-model:value="activeTab">
            <TabList>
                <Tab value="pending">待处理</Tab>
                <Tab value="loading">装货中</Tab>
                <Tab value="transit">运输中</Tab>
                <Tab value="done">已完成</Tab>
                <Tab value="cancelled">已取消</Tab>
            </TabList>

            <TabPanels>
                <TabPanel value="pending">
                    <EntityCardBoard v-if="mounted.pending" :key="`pending-${refreshKey.pending}`"
                        :operations="pendingOps" :columns="OrderColumns" :createColumns="pendingCreateColumns"
                        titleKey="order_id" :gridColumns="4" :allowEdit="false" :allowDelete="false">
                        <template #cardActions="{ item }">
                            <PrimeButton label="分配车辆" size="small" @click.stop="openAssignVehicle(item)" />
                            <PrimeButton label="取消订单" size="small" severity="secondary"
                                @click.stop="onCancelOrder(item)" />
                        </template>
                    </EntityCardBoard>
                </TabPanel>

                <TabPanel value="loading">
                    <EntityCardBoard v-if="mounted.loading" :key="`loading-${refreshKey.loading}`"
                        :operations="loadingOps" :columns="OrderColumns" titleKey="order_id" :gridColumns="4"
                        :allowCreate="false" :allowEdit="false" :allowDelete="false">
                        <template #cardActions="{ item }">
                            <PrimeButton label="取消订单" size="small" severity="secondary"
                                @click.stop="onCancelOrder(item)" />
                        </template>
                    </EntityCardBoard>
                </TabPanel>

                <TabPanel value="transit">
                    <EntityCardBoard v-if="mounted.transit" :key="`transit-${refreshKey.transit}`"
                        :operations="transitOps" :columns="OrderColumns" titleKey="order_id" :gridColumns="4"
                        :allowCreate="false" :allowEdit="false" :allowDelete="false">
                        <template #cardActions="{ item }">
                            <PrimeButton label="取消订单" size="small" severity="secondary"
                                @click.stop="onCancelOrder(item)" />
                        </template>
                    </EntityCardBoard>
                </TabPanel>

                <TabPanel value="done">
                    <EntityCardBoard v-if="mounted.done" :key="`done-${refreshKey.done}`" :operations="doneOps"
                        :columns="OrderColumns" titleKey="order_id" :gridColumns="4" :allowCreate="false"
                        :allowEdit="false" :allowDelete="false">
                    </EntityCardBoard>
                </TabPanel>

                <TabPanel value="cancelled">
                    <EntityCardBoard v-if="mounted.cancelled" :key="`cancelled-${refreshKey.cancelled}`"
                        :operations="cancelledOps" :columns="OrderColumns" titleKey="order_id" :gridColumns="4"
                        :allowCreate="false" :allowEdit="false" :allowDelete="false" />
                </TabPanel>
            </TabPanels>
        </Tabs>

        <PrimeDialog v-model:visible="assignVisible" modal header="分配车辆" :style="{ width: '52rem' }">
            <div class="flex flex-col gap-3">
                <div class="text-sm text-gray-600">
                    订单号：{{ assigningOrder?.order_id ?? '-' }}
                </div>
                <div class="flex flex-col gap-2">
                    <label class="text-sm font-medium text-gray-700">选择车牌号</label>
                    <AutoComplete v-model="selectedVehicle" class="w-full" inputClass="w-full" :delay="300"
                        :forceSelection="true" :suggestions="vehicleSuggestions" optionLabel="vehicle_id" :minLength="0"
                        :completeOnFocus="true" @complete="completeVehicle($event.query)">
                        <template #option="{ option }">
                            <div class="flex flex-col">
                                <span>{{ String(option?.vehicle_id ?? '') }}</span>
                                <span class="text-xs text-gray-500">
                                    状态：{{ String(option?.vehicle_status ?? '') }}
                                    <span v-if="option?.remaining_weight != null">｜剩余载重：{{
                                        String(option?.remaining_weight) }}</span>
                                    <span v-if="option?.remaining_volume != null">｜剩余容积：{{
                                        String(option?.remaining_volume) }}</span>
                                </span>
                            </div>
                        </template>
                    </AutoComplete>
                </div>
            </div>

            <template #footer>
                <PrimeButton label="取消" severity="secondary" @click="assignVisible = false" />
                <PrimeButton label="确认" :loading="assigning" @click="confirmAssignVehicle" />
            </template>
        </PrimeDialog>
    </div>
</template>