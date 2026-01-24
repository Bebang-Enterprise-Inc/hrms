<template>
	<ion-page>
		<ion-header>
			<ion-toolbar>
				<ion-buttons slot="start">
					<ion-back-button :default-href="`/dispatch/trip/${id}`" />
				</ion-buttons>
				<ion-title>Delivery Stop</ion-title>
			</ion-toolbar>
		</ion-header>

		<ion-content :fullscreen="true">
			<div class="p-4">
				<!-- Stop Info -->
				<div class="bg-blue-50 p-4 rounded-lg mb-4">
					<h2 class="text-lg font-bold">Stop {{ stopIdx }}</h2>
					<p class="text-gray-600">Confirm delivery at this location</p>
				</div>

				<!-- Delivery Confirmation Section -->
				<div class="mb-6">
					<h3 class="font-medium mb-3">Delivery Confirmation</h3>

					<div class="mb-4">
						<ion-label class="text-sm text-gray-600 mb-1 block">Received By *</ion-label>
						<ion-input v-model="delivery.signed_by" placeholder="Name of person receiving" />
					</div>

					<!-- Signature Placeholder -->
					<div class="mb-4">
						<ion-label class="text-sm text-gray-600 mb-1 block">Signature</ion-label>
						<div class="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center bg-gray-50">
							<p class="text-gray-500">Tap to capture signature</p>
						</div>
					</div>
				</div>

				<!-- Action Buttons -->
				<div class="space-y-3">
					<ion-button expand="block" @click="confirmDelivery" :disabled="!delivery.signed_by || submitting">
						<ion-spinner v-if="submitting && actionType === 'deliver'" slot="start" />
						Confirm Delivery
					</ion-button>

					<ion-button expand="block" fill="outline" color="warning" @click="showExceptionModal = true">
						Report Exception
					</ion-button>
				</div>
			</div>
		</ion-content>

		<!-- Exception Modal -->
		<ion-modal :is-open="showExceptionModal" @didDismiss="showExceptionModal = false">
			<ion-header>
				<ion-toolbar>
					<ion-title>Report Exception</ion-title>
					<ion-buttons slot="end">
						<ion-button @click="showExceptionModal = false">Close</ion-button>
					</ion-buttons>
				</ion-toolbar>
			</ion-header>
			<ion-content class="ion-padding">
				<div class="mb-4">
					<ion-label class="text-sm text-gray-600 mb-1 block">Exception Type *</ion-label>
					<ion-select v-model="exception.type" interface="action-sheet">
						<ion-select-option value="Store Closed">Store Closed</ion-select-option>
						<ion-select-option value="Refused">Refused Delivery</ion-select-option>
					</ion-select>
				</div>

				<div class="mb-4">
					<ion-label class="text-sm text-gray-600 mb-1 block">Reason</ion-label>
					<ion-textarea v-model="exception.reason" placeholder="Explain the situation..." :rows="4" />
				</div>

				<ion-button expand="block" @click="reportException" :disabled="!exception.type || submitting">
					<ion-spinner v-if="submitting && actionType === 'exception'" slot="start" />
					Submit Exception
				</ion-button>
			</ion-content>
		</ion-modal>
	</ion-page>
</template>

<script setup>
import {
	IonPage, IonHeader, IonToolbar, IonTitle, IonContent, IonButtons,
	IonBackButton, IonButton, IonInput, IonLabel, IonModal,
	IonSpinner, IonSelect, IonSelectOption, IonTextarea
} from "@ionic/vue"
import { ref } from "vue"
import { useRouter } from "vue-router"
import { call } from "frappe-ui"

const router = useRouter()

const props = defineProps({
	id: { type: String, required: true },
	stopIdx: { type: String, required: true }
})

const submitting = ref(false)
const actionType = ref("")
const showExceptionModal = ref(false)

const delivery = ref({
	signed_by: "",
	signature: null
})

const exception = ref({
	type: "",
	reason: ""
})

async function confirmDelivery() {
	if (!delivery.value.signed_by) return

	submitting.value = true
	actionType.value = "deliver"
	try {
		const result = await call("hrms.api.dispatch.confirm_delivery", {
			trip_name: props.id,
			stop_idx: props.stopIdx,
			signed_by: delivery.value.signed_by,
			signature: delivery.value.signature
		})

		if (result?.success) {
			router.push(`/dispatch/trip/${props.id}`)
		}
	} catch (error) {
		console.error("Failed to confirm delivery:", error)
	} finally {
		submitting.value = false
	}
}

async function reportException() {
	if (!exception.value.type) return

	submitting.value = true
	actionType.value = "exception"
	try {
		const result = await call("hrms.api.dispatch.report_exception", {
			trip_name: props.id,
			stop_idx: props.stopIdx,
			exception_type: exception.value.type,
			reason: exception.value.reason
		})

		if (result?.success) {
			showExceptionModal.value = false
			router.push(`/dispatch/trip/${props.id}`)
		}
	} catch (error) {
		console.error("Failed to report exception:", error)
	} finally {
		submitting.value = false
	}
}
</script>
