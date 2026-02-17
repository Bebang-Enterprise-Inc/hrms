<template>
	<ion-page>
		<ion-header>
			<ion-toolbar>
				<ion-buttons slot="start">
					<ion-back-button default-href="/home" />
				</ion-buttons>
				<ion-title>Store Ordering</ion-title>
				<ion-buttons slot="end">
					<ion-button @click="createNewOrder">
						<ion-icon :icon="addOutline" />
					</ion-button>
				</ion-buttons>
			</ion-toolbar>
		</ion-header>

		<ion-content :fullscreen="true">
			<!-- Order Stats -->
			<div class="p-4 bg-gray-50">
				<div class="grid grid-cols-2 gap-3">
					<div class="bg-white p-3 rounded-lg shadow-sm">
						<div class="text-2xl font-bold text-blue-600">{{ stats.pending }}</div>
						<div class="text-sm text-gray-500">Pending Approval</div>
					</div>
					<div class="bg-white p-3 rounded-lg shadow-sm">
						<div class="text-2xl font-bold text-green-600">{{ stats.approved }}</div>
						<div class="text-sm text-gray-500">Approved Today</div>
					</div>
				</div>
			</div>

			<!-- Order Cutoff Warning -->
			<div v-if="showCutoffWarning" class="mx-4 mt-4 p-3 bg-yellow-100 border border-yellow-300 rounded-lg">
				<div class="flex items-center gap-2">
					<ion-icon :icon="timeOutline" class="text-yellow-600" />
					<span class="text-sm text-yellow-800">
						Order cutoff at 12:00 PM. {{ cutoffTimeRemaining }} remaining.
					</span>
				</div>
			</div>

			<!-- Order List -->
			<ion-list>
				<ion-list-header>
					<ion-label>Recent Orders</ion-label>
				</ion-list-header>

				<div v-if="orders.loading" class="flex justify-center p-8">
					<ion-spinner />
				</div>

				<ion-item v-for="order in orders.data?.orders || []" :key="order.name"
					button @click="viewOrder(order.name)">
					<ion-label>
						<h2>{{ order.name }}</h2>
						<p>{{ order.order_date }} - {{ order.item_count }} items</p>
					</ion-label>
					<ion-badge slot="end" :color="getStatusColor(order.status)">
						{{ order.status }}
					</ion-badge>
				</ion-item>

				<EmptyState
					v-if="!orders.loading && (!orders.data?.orders || orders.data.orders.length === 0)"
					message="No orders found"
					buttonLabel="Create Order"
					@action="createNewOrder"
				/>
			</ion-list>

			<!-- FAB for new order -->
			<ion-fab vertical="bottom" horizontal="end" slot="fixed">
				<ion-fab-button @click="createNewOrder">
					<ion-icon :icon="addOutline" />
				</ion-fab-button>
			</ion-fab>
		</ion-content>
	</ion-page>
</template>

<script setup>
import {
	IonPage, IonHeader, IonToolbar, IonTitle, IonContent, IonButtons,
	IonBackButton, IonButton, IonIcon, IonList, IonListHeader, IonLabel,
	IonItem, IonBadge, IonSpinner, IonFab, IonFabButton
} from "@ionic/vue"
import { addOutline, timeOutline } from "ionicons/icons"
import { createResource } from "frappe-ui"
import { ref, computed, inject, onMounted } from "vue"
import { useRouter } from "vue-router"
import EmptyState from "@/components/EmptyState.vue"

const router = useRouter()
const dayjs = inject("$dayjs")
const employee = inject("$employee")

// Stats
const stats = ref({
	pending: 0,
	approved: 0
})

// Cutoff time logic (12:00 PM)
const showCutoffWarning = computed(() => {
	const now = dayjs()
	const cutoff = dayjs().hour(12).minute(0)
	return now.isBefore(cutoff) && now.hour() >= 9
})

const cutoffTimeRemaining = computed(() => {
	const now = dayjs()
	const cutoff = dayjs().hour(12).minute(0)
	if (now.isAfter(cutoff)) return "0m"
	const diff = cutoff.diff(now, "minute")
	const hours = Math.floor(diff / 60)
	const mins = diff % 60
	return hours > 0 ? `${hours}h ${mins}m` : `${mins}m`
})

// Get store from employee's branch
const store = computed(() => employee.data?.branch || "")

// Fetch orders
const orders = createResource({
	url: "hrms.api.store.get_order_history",
	params: { store: store.value, limit: 20 },
	onSuccess(data) {
		// Calculate stats
		if (data?.orders) {
			stats.value.pending = data.orders.filter(o => o.status === "Pending Approval").length
			stats.value.approved = data.orders.filter(o => o.status === "Approved").length
		}
	}
})

function createNewOrder() {
	router.push("/store/ordering/new")
}

function viewOrder(orderId) {
	router.push(`/store/ordering/${orderId}`)
}

function getStatusColor(status) {
	const colors = {
		"Draft": "medium",
		"Pending Approval": "warning",
		"Approved": "success",
		"Partial": "tertiary",
		"Delivered": "primary"
	}
	return colors[status] || "medium"
}

onMounted(() => {
	if (store.value) {
		orders.fetch({ store: store.value, limit: 20 })
	}
})
</script>
