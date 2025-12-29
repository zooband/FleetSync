<script lang="ts">
import { defineComponent } from 'vue'
import InputText from 'primevue/inputtext'

export default defineComponent({
    name: 'SearchBox',
    components: { InputText },
    props: {
        modelValue: { type: String, default: '' },
        size: { type: String as () => 'large' | 'compact', default: 'compact' },
        placeholder: { type: String, default: '搜索书名 / 作者 / 出版社' },
        disabled: { type: Boolean, default: false },
    },
    emits: ['update:modelValue', 'search'],
    computed: {
        isLarge(): boolean {
            return this.size === 'large'
        },
    },
    methods: {
        onEnter(e: KeyboardEvent) {
            if (e.key === 'Enter') this.$emit('search', this.modelValue?.trim() ?? '')
        },
        doSearch() {
            this.$emit('search', this.modelValue?.trim() ?? '')
        },
        update(val: string | undefined) {
            this.$emit('update:modelValue', val ?? '')
        },
    },
})
</script>

<template>
    <div :class="[
        'w-full',
        isLarge ? 'max-w-2xl' : 'max-w-3xl',
    ]">
        <div :class="[
            'flex items-center gap-2',
            'rounded-full border border-gray-300',
            'bg-white',
            'transition-all duration-200',
            'hover:shadow-md focus-within:shadow-md',
            isLarge ? 'px-5 py-3' : 'px-4 py-2',
        ]">
            <i class="pi pi-search text-gray-400"></i>
            <InputText :modelValue="modelValue" @update:modelValue="update" :placeholder="placeholder"
                :disabled="disabled"
                class="search-input flex-1 border-0 focus:ring-0 focus:outline-none p-0 bg-transparent"
                @keydown="onEnter" />
        </div>
    </div>
</template>

<style scoped>
.search-input {
    box-shadow: none !important;
    border: none !important;
    outline: none !important;
}

.search-input :deep(.p-inputtext) {
    border: none !important;
    box-shadow: none !important;
    outline: none !important;
    background: transparent !important;
}

.search-input :deep(.p-inputtext:enabled:focus) {
    box-shadow: none !important;
    border-color: transparent !important;
}

.search-container:focus-within {
    box-shadow: 0 1px 6px rgba(32, 33, 36, 0.28);
    border-color: rgba(223, 225, 229, 0);
}
</style>