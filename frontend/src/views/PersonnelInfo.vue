<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import DatePicker from 'primevue/datepicker'
import PrimeButton from 'primevue/button'
import PrimeDialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import { useToast } from 'primevue/usetoast'
import DBtable from '@/components/DBtable.vue'
import type { Columns, Order, Incident, Personnel, Driver, FleetManager } from '@/types'
import { PersonnelColumns, DriverColumns, FleetManagerColumns, OrderColumns, IncidentColumns } from '@/types'
import { apiFetch, apiJson } from '@/services/api'
import { auth } from '@/services/auth'

type PersonUnion = Personnel | Driver | FleetManager

const route = useRoute()

const personId = computed(() => {
    const raw = route.params.personId
    const n = typeof raw === 'string' ? Number(raw) : Array.isArray(raw) ? Number(raw[0]) : Number(raw)
    return Number.isFinite(n) ? n : NaN
})

const person = ref<PersonUnion | null>(null)

const isAdmin = computed(() => auth.value?.role === 'admin')

const isDriver = computed(() => (person.value as Record<string, unknown> | null)?.['person_role'] === '司机')
const displayedColumns = computed<readonly Columns[]>(() => {
    const role = (person.value as Record<string, unknown> | null)?.['person_role']
    if (role === '司机') return DriverColumns
    if (role === '调度主管') return FleetManagerColumns
    return PersonnelColumns
})

function toDateString(d: Date | null): string {
    if (!d) return ''
    const y = d.getFullYear()
    const m = `${d.getMonth() + 1}`.padStart(2, '0')
    const day = `${d.getDate()}`.padStart(2, '0')
    return `${y}-${m}-${day}`
}

// 筛选时间段（仅司机可见）
const startDate = ref<Date | null>(null)
const endDate = ref<Date | null>(null)

const filterKey = computed(() => `driver-${personId.value}-${toDateString(startDate.value)}-${toDateString(endDate.value)}`)

// 司机订单与异常的列表数据
const driverOrders = ref<Order[]>([])
const driverOrdersTotal = ref(0)
const driverIncidents = ref<Incident[]>([])
const driverIncidentsTotal = ref(0)

type PaginatedResponse<T> = { data: T[]; total: number }

async function fetchPerson() {
    if (!Number.isFinite(personId.value)) return
    person.value = await apiJson<PersonUnion>(`/api/personnels/${personId.value}`)
}

async function searchDriverOrders(_query: string, limit: number, offset: number) {
    if (!Number.isFinite(personId.value)) throw new Error('无效的人员ID')
    const params = new URLSearchParams({
        start: toDateString(startDate.value),
        end: toDateString(endDate.value),
        limit: String(limit),
        offset: String(offset),
    })
    const data = await apiJson<PaginatedResponse<Order>>(`/api/personnels/${personId.value}/orders?${params}`)
    driverOrders.value = data.data
    driverOrdersTotal.value = data.total
}

async function searchDriverIncidents(_query: string, limit: number, offset: number) {
    if (!Number.isFinite(personId.value)) throw new Error('无效的人员ID')
    const params = new URLSearchParams({
        start: toDateString(startDate.value),
        end: toDateString(endDate.value),
        limit: String(limit),
        offset: String(offset),
    })
    const data = await apiJson<PaginatedResponse<Incident>>(`/api/personnels/${personId.value}/incidents?${params}`)
    driverIncidents.value = data.data
    driverIncidentsTotal.value = data.total
}

const ordersOps = {
    get data() { return driverOrders.value },
    get total() { return driverOrdersTotal.value },
    search: searchDriverOrders,
} as const

const incidentsOps = {
    get data() { return driverIncidents.value },
    get total() { return driverIncidentsTotal.value },
    search: searchDriverIncidents,
} as const

function displayValue(value: unknown): string {
    if (value == null) return '无'
    if (typeof value === 'string') {
        const s = value.trim()
        return s.length > 0 ? s : '无'
    }
    return String(value)
}

// 司机信息编辑（仅 admin，且只允许编辑 姓名/联系方式/驾照等级）
const editVisible = ref(false)
const editSubmitting = ref(false)
const editName = ref('')
const editContact = ref('')
const editLicense = ref('')

const driverLicenseOptions = ['A2', 'B2', 'C1', 'C2', 'C3', 'C4', 'C6'] as const

const toast = useToast()

function openEditDriver() {
    if (!isAdmin.value || !isDriver.value) return
    editName.value = String((person.value as any)?.person_name ?? '').trim()
    editContact.value = String((person.value as any)?.person_contact ?? '')
    editLicense.value = String((person.value as any)?.driver_license ?? '').trim()
    editVisible.value = true
}

async function confirmEditDriver() {
    if (!Number.isFinite(personId.value)) throw new Error('无效的人员ID')
    const payload = {
        person_name: editName.value.trim(),
        person_contact: editContact.value.trim() ? editContact.value.trim() : null,
        driver_license: editLicense.value.trim(),
    }
    if (!payload.person_name) throw new Error('请填写姓名')
    if (!payload.driver_license) throw new Error('请选择驾照等级')

    editSubmitting.value = true
    try {
        const res = await apiFetch(`/api/personnels/${personId.value}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        })
        if (!res.ok) {
            const msg = await res.text().catch(() => '')
            throw new Error(msg || '更新司机信息失败')
        }
        editVisible.value = false
        await fetchPerson()
        toast.add({ severity: 'success', summary: '成功', detail: '司机信息已更新', life: 1500 })
    } catch (e) {
        toast.add({ severity: 'error', summary: '错误', detail: (e as Error).message || '操作失败' })
        throw e
    } finally {
        editSubmitting.value = false
    }
}

onMounted(() => {
    fetchPerson().catch((e) => console.error(e))
})
</script>

<template>
    <div class="p-6 space-y-6">
        <div class="flex items-center justify-between">
            <h2 class="text-xl font-bold">人员信息详情（ID：{{ Number.isFinite(personId) ? personId : '-' }}）</h2>
            <PrimeButton v-if="isAdmin && isDriver" size="small" label="编辑司机信息" @click="openEditDriver" />
        </div>

        <!-- 基本信息：根据角色动态选择字段 -->
        <div class="grid grid-cols-2 gap-4">
            <div v-for="col in displayedColumns" :key="col.key" class="flex flex-col">
                <span class="text-sm text-gray-500">{{ col.label }}</span>
                <span class="text-base">{{ person ? displayValue((person as Record<string, unknown>)[col.key]) : ''
                }}</span>
            </div>
        </div>

        <!-- 司机绩效追踪：时间段筛选 + 两张表 -->
        <template v-if="isDriver">
            <div class="flex items-center gap-4">
                <div class="flex flex-col">
                    <span class="text-sm text-gray-500">起始日期</span>
                    <DatePicker v-model="startDate" dateFormat="yy-mm-dd" showIcon />
                </div>
                <div class="flex flex-col">
                    <span class="text-sm text-gray-500">结束日期</span>
                    <DatePicker v-model="endDate" dateFormat="yy-mm-dd" showIcon />
                </div>
            </div>

            <div class="space-y-6">
                <div>
                    <h3 class="text-lg font-semibold mb-2">运输详情</h3>
                    <DBtable :key="`orders-${filterKey}`" :operations="ordersOps" :columns="OrderColumns"
                        :allowCreate="false" :allowEdit="false" :allowDelete="false" />
                </div>

                <div>
                    <h3 class="text-lg font-semibold mb-2">异常记录详情</h3>
                    <DBtable :key="`incidents-${filterKey}`" :operations="incidentsOps" :columns="IncidentColumns"
                        :allowCreate="false" :allowEdit="false" :allowDelete="false" />
                </div>
            </div>
        </template>

        <PrimeDialog v-model:visible="editVisible" modal header="编辑司机信息" :style="{ width: '36rem' }">
            <div class="grid grid-cols-2 gap-4">
                <div class="flex flex-col gap-2">
                    <label class="text-sm font-medium text-gray-700 dark:text-gray-300">姓名*</label>
                    <InputText v-model="editName" />
                </div>
                <div class="flex flex-col gap-2">
                    <label class="text-sm font-medium text-gray-700 dark:text-gray-300">联系方式</label>
                    <InputText v-model="editContact" />
                </div>
                <div class="flex flex-col gap-2 col-span-2">
                    <label class="text-sm font-medium text-gray-700 dark:text-gray-300">驾照等级*</label>
                    <Select v-model="editLicense" :options="[...driverLicenseOptions]" class="w-full" />
                </div>
            </div>

            <template #footer>
                <PrimeButton label="取消" severity="secondary" @click="editVisible = false" />
                <PrimeButton label="确认" :loading="editSubmitting" @click="confirmEditDriver" />
            </template>
        </PrimeDialog>
    </div>
</template>
