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

				<!-- GAP-092: Pre-delivery billing exception workflow -->
				<div class="mb-6 border border-amber-200 bg-amber-50 rounded-lg p-4">
					<h3 class="font-medium mb-2">Pre-Delivery Billing (Dual Approval)</h3>
					<p class="text-xs text-gray-700 mb-3">
						Use only for approved exception cases. Requires Daymae/CPO + Butch/CFO approval before billing can be created.
					</p>

					<div class="mb-3">
						<ion-label class="text-sm text-gray-600 mb-1 block">Exception Reason *</ion-label>
						<ion-textarea
							v-model="preDelivery.reason"
							placeholder="Explain why billing is needed before delivery confirmation..."
							:rows="3"
						/>
					</div>

					<div class="space-y-2">
						<ion-button
							expand="block"
							fill="outline"
							color="warning"
							@click="requestPreDeliveryException"
							:disabled="!preDelivery.reason || submitting"
						>
							<ion-spinner v-if="submitting && actionType === 'request-pre-billing'" slot="start" />
							Request Dual-Approval Exception
						</ion-button>

						<ion-button
							expand="block"
							fill="outline"
							color="medium"
							@click="refreshPreDeliveryStatus"
							:disabled="submitting"
						>
							<ion-spinner v-if="submitting && actionType === 'refresh-pre-billing'" slot="start" />
							Refresh Exception Status
						</ion-button>

						<ion-button
							expand="block"
							color="tertiary"
							@click="createPreDeliveryBilling"
							:disabled="!canCreatePreDeliveryBilling || submitting"
						>
							<ion-spinner v-if="submitting && actionType === 'create-pre-billing'" slot="start" />
							Create Pre-Delivery Billing
						</ion-button>
					</div>

					<div v-if="preDelivery.statusText" class="text-xs text-gray-700 mt-3">
						Status: {{ preDelivery.statusText }}
					</div>
					<div v-if="preDelivery.billingReference" class="text-xs text-green-700 mt-1">
						Billing Created: {{ preDelivery.billingReference }}
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
import { computed, onMounted, ref } from "vue"
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
const preDelivery = ref({
	reason: "",
	latestException: null,
	statusText: "",
	billingReference: ""
})
const canCreatePreDeliveryBilling = computed(() => {
	return Boolean(preDelivery.value.latestException?.name) &&
		preDelivery.value.latestException?.status === "Approved" &&
		!preDelivery.value.billingReference
})

function _normalizeError(error) {
	if (typeof error === "string") return error
	if (error?.messages && Array.isArray(error.messages)) return error.messages.join("; ")
	return error?.message || "Operation failed"
}

function _setBusy(type) {
	submitting.value = true
	actionType.value = type
}

async function confirmDelivery() {
	if (!delivery.value.signed_by) return

	_setBusy("deliver")
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

	_setBusy("exception")
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

async function refreshPreDeliveryStatus() {
	_setBusy("refresh-pre-billing")
	try {
		const result = await call("hrms.api.dispatch.get_pre_delivery_billing_exception_status", {
			trip_name: props.id,
			stop_idx: props.stopIdx
		})
		preDelivery.value.latestException = result?.latest || null
		const latest = preDelivery.value.latestException
		if (!latest) {
			preDelivery.value.statusText = "No exception request found yet."
			return
		}
		preDelivery.value.statusText = `${latest.status || "Pending"} (${latest.name})`
	} catch (error) {
		preDelivery.value.statusText = _normalizeError(error)
	} finally {
		submitting.value = false
	}
}

async function requestPreDeliveryException() {
	if (!preDelivery.value.reason) return

	_setBusy("request-pre-billing")
	try {
		await call("hrms.api.dispatch.request_pre_delivery_billing_exception", {
			trip_name: props.id,
			stop_idx: props.stopIdx,
			reason: preDelivery.value.reason
		})
		preDelivery.value.statusText = "Exception request submitted."
	} catch (error) {
		preDelivery.value.statusText = _normalizeError(error)
	} finally {
		submitting.value = false
	}

	await refreshPreDeliveryStatus()
}

async function createPreDeliveryBilling() {
	const exceptionName = preDelivery.value.latestException?.name
	if (!exceptionName) {
		preDelivery.value.statusText = "Approved exception is required before creating pre-delivery billing."
		return
	}

	_setBusy("create-pre-billing")
	try {
		const result = await call("hrms.api.dispatch.create_pre_delivery_billing", {
			trip_name: props.id,
			stop_idx: props.stopIdx,
			pre_delivery_exception: exceptionName
		})
		preDelivery.value.billingReference = result?.billing_reference || ""
		preDelivery.value.statusText = `Pre-delivery billing created (${result?.billing_reference || "no reference"})`
	} catch (error) {
		preDelivery.value.statusText = _normalizeError(error)
	} finally {
		submitting.value = false
	}
}

onMounted(() => {
	refreshPreDeliveryStatus()
})
</script>
