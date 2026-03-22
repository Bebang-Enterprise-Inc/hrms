<template>
	<ion-page>
		<ion-header>
			<ion-toolbar>
				<ion-buttons slot="start">
					<ion-back-button default-href="/store/ordering" />
				</ion-buttons>
				<ion-title>New Order</ion-title>
			</ion-toolbar>
			<!-- Category Tabs -->
			<ion-toolbar>
				<ion-segment v-model="selectedCategory" scrollable>
					<ion-segment-button v-for="cat in categories" :key="cat" :value="cat">
						<ion-label>{{ cat }}</ion-label>
					</ion-segment-button>
				</ion-segment>
			</ion-toolbar>
		</ion-header>

		<ion-content :fullscreen="true">
			<div v-if="items.loading" class="flex justify-center p-8">
				<ion-spinner />
			</div>

			<!-- Item List -->
			<ion-list v-else>
				<ion-item v-for="item in filteredItems" :key="item.name">
					<ion-thumbnail slot="start">
						<img :src="item.image || '/assets/hrms/images/placeholder.png'"
							alt="" class="w-12 h-12 object-cover rounded" />
					</ion-thumbnail>
					<ion-label>
						<h2 class="font-medium">{{ item.item_name }}</h2>
						<p class="text-gray-500">{{ item.stock_uom }}</p>
						<p v-if="item.last_order_qty" class="text-xs text-blue-500">
							Last order: {{ item.last_order_qty }}
						</p>
					</ion-label>
					<div class="flex items-center gap-2" slot="end">
						<ion-button fill="clear" size="small" @click="decrementQty(item.name)"
							:disabled="!orderItems[item.name]">
							<ion-icon :icon="removeOutline" />
						</ion-button>
						<span class="w-10 text-center font-bold">
							{{ orderItems[item.name] || 0 }}
						</span>
						<ion-button fill="clear" size="small" @click="incrementQty(item.name)">
							<ion-icon :icon="addOutline" />
						</ion-button>
					</div>
				</ion-item>
			</ion-list>

			<!-- Order Summary FAB -->
			<ion-fab v-if="totalItems > 0" vertical="bottom" horizontal="center" slot="fixed">
				<ion-fab-button @click="reviewOrder" class="w-48">
					<span class="text-sm">Review Order ({{ totalItems }} items)</span>
				</ion-fab-button>
			</ion-fab>
		</ion-content>

		<!-- Review Order Modal -->
		<ion-modal :is-open="showReviewModal" @didDismiss="showReviewModal = false">
			<ion-header>
				<ion-toolbar>
					<ion-title>Review Order</ion-title>
					<ion-buttons slot="end">
						<ion-button @click="showReviewModal = false">Close</ion-button>
					</ion-buttons>
				</ion-toolbar>
			</ion-header>
			<ion-content>
				<ion-list>
					<ion-item v-for="(qty, itemName) in orderItems" :key="itemName" v-show="qty > 0">
						<ion-label>
							<h2>{{ getItemName(itemName) }}</h2>
						</ion-label>
						<ion-note slot="end">{{ qty }}</ion-note>
					</ion-item>
				</ion-list>
				<div class="p-4">
					<ion-button expand="block" @click="submitOrder" :disabled="submitting">
						<ion-spinner v-if="submitting" slot="start" />
						Submit Order
					</ion-button>
				</div>
			</ion-content>
		</ion-modal>
	</ion-page>
</template>

<script setup>
import {
	IonPage, IonHeader, IonToolbar, IonTitle, IonContent, IonButtons,
	IonBackButton, IonButton, IonIcon, IonList, IonLabel, IonItem,
	IonSpinner, IonFab, IonFabButton, IonSegment, IonSegmentButton,
	IonThumbnail, IonNote, IonModal
} from "@ionic/vue"
import { addOutline, removeOutline } from "ionicons/icons"
import { createResource, call } from "frappe-ui"
import { ref, computed, inject, onMounted } from "vue"
import { useRouter } from "vue-router"

const router = useRouter()
const employee = inject("$employee")

const selectedCategory = ref("All")
const categories = computed(() => {
	if (!items.data) return ["All"]
	const groups = [...new Set(items.data.map(i => i.item_group).filter(Boolean))]
	groups.sort()
	return ["All", ...groups]
})
const orderItems = ref({})
const showReviewModal = ref(false)
const submitting = ref(false)

// Get store from employee's branch
const store = computed(() => employee.data?.branch || "")

// Fetch orderable items
const items = createResource({
	url: "hrms.api.store.get_orderable_items",
	params: { store: store.value },
	auto: false,
	transform(data) {
		return data?.items || []
	}
})

const filteredItems = computed(() => {
	if (!items.data) return []
	if (selectedCategory.value === "All") return items.data
	return items.data.filter(item => item.item_group === selectedCategory.value)
})

const totalItems = computed(() => {
	return Object.values(orderItems.value).reduce((sum, qty) => sum + (qty || 0), 0)
})

function incrementQty(itemName) {
	if (!orderItems.value[itemName]) {
		orderItems.value[itemName] = 0
	}
	orderItems.value[itemName]++
}

function decrementQty(itemName) {
	if (orderItems.value[itemName] > 0) {
		orderItems.value[itemName]--
	}
}

function getItemName(itemCode) {
	const item = items.data?.find(i => i.name === itemCode)
	return item?.item_name || itemCode
}

function reviewOrder() {
	showReviewModal.value = true
}

async function submitOrder() {
	submitting.value = true
	try {
		const orderItemsList = Object.entries(orderItems.value)
			.filter(([_, qty]) => qty > 0)
			.map(([item_code, qty_requested]) => ({ item_code, qty_requested }))

		const result = await call("hrms.api.store.submit_order", {
			store: store.value,
			items: JSON.stringify(orderItemsList)
		})

		if (result?.success) {
			showReviewModal.value = false
			router.push(`/store/ordering/${result.order}`)
		}
	} catch (error) {
		console.error("Failed to submit order:", error)
	} finally {
		submitting.value = false
	}
}

onMounted(() => {
	if (store.value) {
		items.fetch({ store: store.value })
	}
})
</script>
