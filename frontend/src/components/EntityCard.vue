<script setup lang="ts">
import PrimeButton from 'primevue/button'

const props = withDefaults(
    defineProps<{
        variant?: 'default' | 'add'
        title: string
        subtitle?: string
        subtitleLines?: readonly string[]
        clickable?: boolean
        allowEdit?: boolean
        allowDelete?: boolean
    }>(),
    {
        variant: 'default',
        clickable: true,
        allowEdit: true,
        allowDelete: true,
    }
)

const emit = defineEmits<{
    (e: 'click'): void
    (e: 'edit'): void
    (e: 'delete'): void
}>()

function onCardClick() {
    if (!props.clickable) return
    emit('click')
}
</script>

<template>
    <div class="rounded-lg p-4 transition-colors border border-gray-200 bg-white hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900 dark:hover:bg-gray-800"
        :class="{ 'cursor-pointer': clickable }" role="button" tabindex="0" @click="onCardClick"
        @keydown.enter="onCardClick">
        <!-- 内容区域 -->
        <div class="flex flex-col min-w-0">
            <div class="text-base font-semibold truncate text-gray-900 dark:text-gray-100">{{ title }}</div>

            <!-- Subtitle 或 subtitleLines -->
            <div v-if="subtitleLines && subtitleLines.length > 0" class="mt-1 text-sm text-gray-500 dark:text-gray-400">
                <div v-for="(line, idx) in subtitleLines" :key="idx" class="truncate">{{ line }}</div>
            </div>
            <div v-else-if="subtitle" class="mt-1 text-sm text-gray-500 dark:text-gray-400 truncate">{{ subtitle }}
            </div>

            <!-- 默认插槽内容 -->
            <div v-if="$slots.default" class="mt-3">
                <slot />
            </div>
        </div>

        <!-- 操作按钮区域（仅在 default 模式下显示） -->
        <div v-if="variant === 'default'" class="mt-3 flex gap-2">
            <slot v-if="$slots.actions" name="actions" />
            <PrimeButton v-if="allowEdit" aria-label="编辑" icon="pi pi-pencil" text rounded size="small" @click.stop="emit('edit')" />
            <PrimeButton v-if="allowDelete" aria-label="删除" icon="pi pi-trash" text rounded severity="danger" size="small"
                @click.stop="emit('delete')" />
        </div>

        <!-- Add variant 特殊样式：移除额外外边距，使用最小高度并居中 -->
        <div v-else-if="variant === 'add'" class="flex items-center justify-center py-10 min-h-24">
            <span class="pi pi-plus text-2xl text-gray-500 dark:text-gray-400" aria-label="添加"></span>
        </div>
    </div>
</template>