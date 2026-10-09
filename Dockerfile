# Build on RunPod or an authorized external builder, NOT in the Replit workspace.
FROM runpod/worker-comfyui:5.11.0-sdxl
USER root
ARG ENABLE_FACEID=0
ARG FACEID_LICENSE_CONFIRMED=0
ENV REFERENCE_FACEID_ENABLED=${ENABLE_FACEID}

COPY models.json install_models.py requirements-faceid.txt /opt/reference-worker/
RUN git clone --no-checkout https://github.com/cubiq/ComfyUI_IPAdapter_plus.git /comfyui/custom_nodes/ComfyUI_IPAdapter_plus \
    && cd /comfyui/custom_nodes/ComfyUI_IPAdapter_plus \
    && git checkout a0f451a5113cf9becb0847b92884cb10cbdec0ef

# Off by default: pretrained InsightFace weights have non-commercial restrictions.
# Enabling this requires rights covering the deployment's actual use.
RUN if [ "$ENABLE_FACEID" = "1" ]; then \
      test "$FACEID_LICENSE_CONFIRMED" = "1" \
      && apt-get update \
      && apt-get install -y --no-install-recommends build-essential python3-dev \
      && rm -rf /var/lib/apt/lists/* \
      && uv pip install --python /opt/venv/bin/python numpy==1.26.4 Cython==3.0.12 \
      && uv pip install --python /opt/venv/bin/python --no-build-isolation -r /opt/reference-worker/requirements-faceid.txt; \
    else test "$ENABLE_FACEID" = "0"; fi

RUN /opt/venv/bin/python /opt/reference-worker/install_models.py --root /comfyui
COPY verify_worker.py contract-workflows.json /opt/reference-worker/
# Actual ComfyUI node import and object_info verification, CPU only, no /prompt call.
RUN /opt/venv/bin/python /opt/reference-worker/verify_worker.py --root /comfyui
# Keep the official image's entrypoint, handler, image upload protocol, and CMD.
