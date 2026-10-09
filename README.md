# MangaForge reference worker

This is a worker-only build context. It does not include the app, databases,
artwork, account identifiers, or secrets. Build it with RunPod's GitHub
integration or an authorized external builder, not inside Replit.

## Supported profile

The default profile targets **SDXL** and includes:

- RunPod ComfyUI worker `5.11.0-sdxl`, retaining its original handler/entrypoint.
- IPAdapter Plus commit `a0f451a5113cf9becb0847b92884cb10cbdec0ef`.
- ViT-H vision encoder, SDXL Plus style and Plus Face portrait adapters.
- SDXL depth ControlNet (FP16 safetensors, renamed to the application contract).

Model URLs use immutable Hugging Face revisions. The download step verifies
their SHA-256 and sizes. Additional default models total approximately 6.7 GB;
the final image also includes the stock SDXL checkpoint, VAE, CUDA and Python
libraries. Do not assume the existing 20 GB disk is sufficient: use the final
build size and runtime free space to agree on any increase before deployment.

**Canonical/rolling character reference conditioning is not FaceID.** The
default profile supports image-based character matching without InsightFace.
Existing depth maps are supported; depth-map extraction (`Zoe-DepthMapPreprocessor`)
and lighting preprocessing (`ColorCorrect`) are separate extensions, not
claimed by this profile.

## Optional FaceID profile: license and compatibility gates

FaceID is off by default. InsightFace's pretrained weights and the FaceID
model card restrict use; consult
[InsightFace licensing](https://github.com/deepinsight/insightface#license)
and the [FaceID model card](https://huggingface.co/h94/IP-Adapter-FaceID).
Do not enable these pretrained models in commercial production without rights
covering that use. The confirmation flag is not a license grant.

Only after confirming appropriate rights, build with `ENABLE_FACEID=1` and
`FACEID_LICENSE_CONFIRMED=1`. This installs InsightFace/ONNX Runtime, the
SDXL FaceID Plus V2 adapter and its matching LoRA, and the official `v0.7`
Buffalo-L archive. The archive is version-pinned and CRC-checked; unlike the
Hugging Face models, it does not have an independently pinned SHA-256.
Review and hash that archive in your approved build before a production release.

After the FaceID profile passes its build check and a separately authorized
GPU check, set **the application's** `GPU_FACEID_ENABLED=true` through the
workspace environment settings. The worker build argument alone does not
enable it in the app. Saved face references otherwise produce an explicit
error before a panel job/allowance is created; they are never ignored.

The corrected workflow uses `IPAdapterUnifiedLoaderFaceID` to pair the correct
model/LoRA/InsightFace pipeline, and `weight_faceidv2` (not `weight_v2`).
Legacy serialized ReActor face models are not images. If a character has only
such a model, re-extract an approved face-reference image with a compatible
extraction workflow first. The legacy `CropFace`/ReActor extraction workflow
is not made compatible merely by installing IPAdapter; do not submit it to
this profile without supplying and checking its own extensions.

## Build on RunPod

1. In RunPod **Settings → Connections → GitHub**, connect GitHub and select
   **only this worker repository**. Replit's GitHub authorization does
   not authorize RunPod's separate GitHub app. Public repository visibility
   does not replace this authorization.
2. Prepare the repository configuration in RunPod: branch `main`, context `/`,
   Dockerfile `Dockerfile`, endpoint type **Queue**. Do not click deploy or
   attach the build to a live endpoint until the operator has approved the
   resource/downtime consequences.
3. Preserve the existing GPU pools, min/max workers, idle timeout, scaling,
   timeout, volumes and environment variables. If staging requires a new
   endpoint, obtain approval for that additional resource and its limits first.
4. Start the approved build. GitHub commits alone do not trigger endpoint
   updates; creating a GitHub release does. Do not create a release until
   deployment is approved. In **Builds**, require
   `REFERENCE_WORKER_BUILD_CHECK` with style, character, combined-depth and
   sheet checks. It must report `sampling_performed:false`.
5. Save the exact built image reference/digest and build logs. A CPU schema
   check is not proof that GPU inference works. Obtain separate approval for
   one disposable panel, one variant, no automatic retries, before GPU testing.
6. Switch the approved target endpoint to the built image without replacing
   unrelated configuration. Allow cold startup and inspect health/errors.

For a manual authorized builder the equivalent command is:

```sh
docker build --platform linux/amd64 -t <your-registry>/mangaforge-reference-worker:<release> .
```

The default build performs no sampling and submits no RunPod jobs. RunPod
builds/deployment self-tests and worker startup may themselves incur provider
charges; approve those before beginning. No GitHub Actions are installed.

## Application alignment and checks

- Both panel and sheet workflows use `IPAdapterAdvanced` with a ViT-H encoder.
- Missing optional image inputs are omitted, not supplied as null.
- SD1.5 depth model overrides are rejected for the SDXL reference workflow.
- Large casts cannot overwrite the sampler's node ID.
- `contract-workflows.json` is generated from the application's real builders,
  with fictional prompts and placeholder image names, not user artwork.
- `verify_worker.py` imports actual ComfyUI nodes and checks required inputs,
  linked output types and model filename choices. It never calls `/prompt`.

The pinned base image and extension still have inherited transitive
dependencies. Retain the successful image digest and Python dependency freeze
from the external build; do not equate a version tag with a byte-identical
future image.

## Rollback

Keep the original endpoint's image, resource settings and build metadata
privately with the operator before any update. The observed starting image is
`runpod/worker-comfyui:latest-sdxl`; this tag is mutable, so resolve/save its
digest in the provider before relying on it as a rollback target.

Drain or account for active jobs before switching. Restore the previous
image/digest and only settings explicitly changed. For GitHub-managed
endpoints, RunPod's **Builds → previous build → Rollback** restores the prior
build. This is an external worker rollback, not a Replit code checkpoint.
Never delete user panels or references as part of rollback.

Official setup:
https://docs.runpod.io/serverless/workers/github-integration
