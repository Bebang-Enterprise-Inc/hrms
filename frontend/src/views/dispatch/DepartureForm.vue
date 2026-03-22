<template>
	<ion-page>
		<ion-header>
			<ion-toolbar>
				<ion-buttons slot="start">
					<ion-back-button :default-href="`/dispatch/trip/${id}`" />
				</ion-buttons>
				<ion-title>Departure Checklist</ion-title>
			</ion-toolbar>
		</ion-header>

		<ion-content :fullscreen="true">
			<div class="p-4">
				<h2 class="text-lg font-bold mb-4">Pre-Departure Checklist</h2>

				<!-- Driver Selection -->
				<div class="mb-4">
					<ion-label class="text-sm text-gray-600 mb-1 block">Driver *</ion-label>
					<ion-input v-model="departure.driver" placeholder="Enter driver name" />
				</div>

				<!-- Vehicle Info -->
				<div class="grid grid-cols-2 gap-4 mb-4">
					<div>
						<ion-label class="text-sm text-gray-600 mb-1 block">Vehicle</ion-label>
						<ion-input v-model="departure.vehicle" placeholder="Vehicle type" />
					</div>
					<div>
						<ion-label class="text-sm text-gray-600 mb-1 block">Plate Number</ion-label>
						<ion-input v-model="departure.vehicle_plate" placeholder="ABC 123" />
					</div>
				</div>

				<!-- Temperature -->
				<div class="mb-4">
					<ion-label class="text-sm text-gray-600 mb-1 block">Departure Temperature (°C) *</ion-label>
					<ion-input type="number" v-model.number="departure.temperature" placeholder="e.g. 4" />
				</div>

				<!-- Seal Number -->
				<div class="mb-4">
					<ion-label class="text-sm text-gray-600 mb-1 block">Seal Number</ion-label>
					<ion-input v-model="departure.seal_number" placeholder="Enter seal number" />
				</div>

				<!-- Checklist Items -->
				<div class="mb-6">
					<h3 class="font-medium mb-3">Checklist</h3>
					<div class="space-y-2">
						<ion-item v-for="(item, index) in checklist" :key="index" lines="none">
							<ion-checkbox v-model="item.checked" slot="start" />
							<ion-label>{{ item.label }}</ion-label>
						</ion-item>
					</div>
				</div>

				<!-- Submit Button -->
				<ion-button expand="block" @click="confirmDeparture" :disabled="!canSubmit || submitting">
					<ion-spinner v-if="submitting" slot="start" />
					Confirm Departure
				</ion-button>
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import {
	IonPage, IonHeader, IonToolbar, IonTitle, IonContent, IonButtons,
	IonBackButton, IonButton, IonInput, IonLabel, IonItem,
	IonSpinner, IonCheckbox
} from "@ionic/vue"
import { ref, computed } from "vue"
import { useRouter } from "vue-router"
import { call } from "frappe-ui"

const router = useRouter()

const props = defineProps({
	id: { type: String, required: true }
})

const submitting = ref(false)

const departure = ref({
	driver: "",
	vehicle: "",
	vehicle_plate: "",
	temperature: null,
	seal_number: ""
})

const checklist = ref([
	{ label: "Vehicle cleanliness verified", checked: false },
	{ label: "Temperature logger installed", checked: false },
	{ label: "All items loaded and verified", checked: false },
	{ label: "Delivery documents complete", checked: false },
	{ label: "Vehicle inspection completed", checked: false }
])

const canSubmit = computed(() => {
	return departure.value.driver &&
		departure.value.temperature !== null &&
		checklist.value.every(item => item.checked)
})

async function confirmDeparture() {
	if (!canSubmit.value) return

	submitting.value = true
	try {
		const result = await call("hrms.api.dispatch.confirm_departure", {
			trip_name: props.id,
			driver: departure.value.driver,
			vehicle: departure.value.vehicle,
			vehicle_plate: departure.value.vehicle_plate,
			temperature: departure.value.temperature,
			seal_number: departure.value.seal_number
		})

		if (result?.success) {
			router.push(`/dispatch/trip/${props.id}`)
		}
	} catch (error) {
		console.error("Failed to confirm departure:", error)
	} finally {
		submitting.value = false
	}
}
</script>
