using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;

namespace AjArtPipeline
{
    /// <summary>
    /// Headless review capture. Usage:
    /// Unity -batchmode -projectPath P -executeMethod AjArtPipeline.ArtPipelineCapture.Run
    ///       -artModel Assets/Art/Generated/X.fbx -artOut C:/abs/dir
    /// Exit code 0 on success, 1 on any failure (with an [ArtPipeline] ERROR log line).
    /// </summary>
    public static class ArtPipelineCapture
    {
        const int Size = 1024;
        const float CapsuleHeight = 1.8f;

        [Serializable] class MatInfo { public string name; public string shader; public bool hasBaseMap; }
        [Serializable]
        class Stats
        {
            public string model;
            public string rig;
            public bool avatarValid;
            public bool avatarHuman;
            public int triangles;
            public int bones;
            public float[] boundsMin, boundsMax, boundsSize;
            public string[] clips;
            public MatInfo[] materials;
            public string[] images;
        }

        static string Arg(string name)
        {
            var a = Environment.GetCommandLineArgs();
            int i = Array.IndexOf(a, name);
            return i >= 0 && i + 1 < a.Length ? a[i + 1] : null;
        }

        public static void Run()
        {
            try
            {
                string model = Arg("-artModel"), outDir = Arg("-artOut");
                if (string.IsNullOrEmpty(model) || string.IsNullOrEmpty(outDir))
                    throw new Exception("need -artModel <Assets/..fbx> and -artOut <abs dir>");
                Capture(model, outDir);
                Debug.Log("[ArtPipeline] capture OK");
                EditorApplication.Exit(0);
            }
            catch (Exception e)
            {
                Debug.LogError($"[ArtPipeline] ERROR: {e.Message}\n{e.StackTrace}");
                EditorApplication.Exit(1);
            }
        }

        [MenuItem("Tools/Art Pipeline/Capture Selected Model")]
        static void MenuCapture()
        {
            string path = AssetDatabase.GetAssetPath(Selection.activeObject);
            string dir = Path.Combine(Path.GetDirectoryName(Application.dataPath), "Library", "ArtPipelineCapture");
            Capture(path, dir);
            EditorUtility.RevealInFinder(dir);
        }

        public static void Capture(string modelPath, string outDir)
        {
            ArtPipelineSetup.EnsureURP();
            Directory.CreateDirectory(outDir);
            var sc = ArtSidecar.Load(modelPath);
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(modelPath);
            if (prefab == null) throw new Exception($"model not found or not imported: {modelPath}");

            bool humanoid = sc != null && sc.rig == "humanoid";
            var importer = (ModelImporter)AssetImporter.GetAtPath(modelPath);
            // The rest pose / bone map is recorded during an import and takes effect on the next one.
            for (int i = 0; humanoid && i < 3 && !(importer.sourceAvatar != null && importer.sourceAvatar.isValid); i++)
                importer.SaveAndReimport();
            prefab = AssetDatabase.LoadAssetAtPath<GameObject>(modelPath);
            Avatar avatar = AssetDatabase.LoadAllAssetsAtPath(modelPath).OfType<Avatar>().FirstOrDefault();
            if (humanoid && (avatar == null || !avatar.isValid || !avatar.isHuman))
                throw new Exception($"{modelPath}: Humanoid avatar missing or invalid (check bone names against ArtPipelineImporter.HumanBones)");

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var go = (GameObject)PrefabUtility.InstantiatePrefab(prefab);

            var clips = AssetDatabase.LoadAllAssetsAtPath(modelPath).OfType<AnimationClip>()
                .Where(c => !c.name.StartsWith("__preview__")).ToArray();

            Bounds b = MeasureBounds(go, out int tris, out int bones);
            var cap = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            cap.name = "Reference_1.80m";
            cap.transform.localScale = new Vector3(0.5f, CapsuleHeight / 2f, 0.5f); // Unity capsule is 2 m tall
            var lit = Shader.Find(ArtPipelineImporter.LitShaderName);
            Material Mat(Color c) { var m = new Material(lit); m.SetColor("_BaseColor", c); return m; }
            cap.GetComponent<Renderer>().sharedMaterial = Mat(new Color(0.38f, 0.38f, 0.40f));  // neutral: never compete with the asset's palette

            var ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
            ground.transform.localScale = new Vector3(2f, 1f, 2f);
            ground.GetComponent<Renderer>().sharedMaterial = Mat(new Color(0.55f, 0.55f, 0.58f));

            var lightGo = new GameObject("Key Light");
            var light = lightGo.AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.3f;
            light.shadows = LightShadows.Soft;
            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(0.45f, 0.45f, 0.5f);

            var camGo = new GameObject("Cam");
            var cam = camGo.AddComponent<Camera>();
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color(0.72f, 0.78f, 0.85f);
            cam.fieldOfView = 30f;
            cam.nearClipPlane = 0.05f;
            cam.farClipPlane = 200f;

            var images = new List<string>();
            images.Add(Shoot(cam, b, cap.transform, lightGo.transform, 35f, 14f, -1, outDir, "three_quarter"));  // from front-left
            images.Add(Shoot(cam, b, cap.transform, lightGo.transform, 0f, 5f, 0, outDir, "front"));
            images.Add(Shoot(cam, b, cap.transform, lightGo.transform, 90f, 5f, 0, outDir, "side"));

            var walk = clips.FirstOrDefault(c => c.name == "walk");
            if (humanoid && walk != null)
            {
                AnimationMode.StartAnimationMode();
                AnimationMode.SampleAnimationClip(go, walk, walk.length * 0.25f);
                // GPU skinning is cached per frame and we render several shots in one frame: freeze the
                // sampled pose into plain meshes so the walk shot really shows it.
                foreach (var smr in go.GetComponentsInChildren<SkinnedMeshRenderer>())
                {
                    var frozen = new GameObject(smr.name + "_walkpose");
                    var mesh = new Mesh();
                    smr.BakeMesh(mesh, true);
                    frozen.AddComponent<MeshFilter>().sharedMesh = mesh;
                    frozen.AddComponent<MeshRenderer>().sharedMaterials = smr.sharedMaterials;
                    frozen.transform.SetPositionAndRotation(smr.transform.position, smr.transform.rotation);
                    frozen.transform.localScale = smr.transform.lossyScale; // BakeMesh output is in the renderer's local space
                    smr.enabled = false;
                }
                images.Add(Shoot(cam, b, cap.transform, lightGo.transform, 90f, 5f, 0, outDir, "walk"));
            }
            else if (humanoid) Debug.LogWarning("[ArtPipeline] humanoid has no clip named 'walk'; skipping walk frame");

            var mats = go.GetComponentsInChildren<Renderer>().SelectMany(r => r.sharedMaterials).Where(m => m != null).Distinct()
                .Select(m => new MatInfo { name = m.name, shader = m.shader.name, hasBaseMap = m.HasProperty("_BaseMap") && m.GetTexture("_BaseMap") != null }).ToArray();
            var stats = new Stats
            {
                model = modelPath,
                rig = sc?.rig ?? "unconfigured",
                avatarValid = avatar != null && avatar.isValid,
                avatarHuman = avatar != null && avatar.isHuman,
                triangles = tris,
                bones = bones,
                boundsMin = new[] { b.min.x, b.min.y, b.min.z },
                boundsMax = new[] { b.max.x, b.max.y, b.max.z },
                boundsSize = new[] { b.size.x, b.size.y, b.size.z },
                clips = clips.Select(c => $"{c.name} ({c.length:F2}s, loop={c.isLooping})").ToArray(),
                materials = mats,
                images = images.ToArray(),
            };
            File.WriteAllText(Path.Combine(outDir, "stats.json"), JsonUtility.ToJson(stats, true));
            if (mats.Any(m => !m.shader.StartsWith("Universal Render Pipeline")))
                throw new Exception("model has non-URP materials: " + string.Join(", ", mats.Select(m => m.name + "=" + m.shader)));
        }

        static Transform FindDeep(Transform t, string n) => t.GetComponentsInChildren<Transform>().FirstOrDefault(x => x.name == n);

        /// <summary>World bounds from baked vertices (Renderer.bounds is padded for skinned meshes).</summary>
        static Bounds MeasureBounds(GameObject go, out int tris, out int bones)
        {
            bool any = false; var b = new Bounds(); tris = 0;
            var boneSet = new HashSet<Transform>();
            void Add(Vector3 p) { if (!any) { b = new Bounds(p, Vector3.zero); any = true; } else b.Encapsulate(p); }
            foreach (var smr in go.GetComponentsInChildren<SkinnedMeshRenderer>())
            {
                var baked = new Mesh();
                smr.BakeMesh(baked, true);
                var m = smr.transform.localToWorldMatrix;
                foreach (var v in baked.vertices) Add(m.MultiplyPoint3x4(v));
                tris += smr.sharedMesh.triangles.Length / 3;
                foreach (var t in smr.bones) if (t != null) boneSet.Add(t);
            }
            foreach (var mf in go.GetComponentsInChildren<MeshFilter>())
            {
                var m = mf.transform.localToWorldMatrix;
                foreach (var v in mf.sharedMesh.vertices) Add(m.MultiplyPoint3x4(v));
                tris += mf.sharedMesh.triangles.Length / 3;
            }
            if (!any) throw new Exception("model has no meshes");
            bones = boneSet.Count;
            return b;
        }

        /// <summary>
        /// Orbit the camera around the model. yaw 0 = looking from +Z, 90 = from -X; flip -1 mirrors yaw.
        /// The 1.80 m capsule is put to the camera's right at the model's depth so scale reads true.
        /// </summary>
        static string Shoot(Camera cam, Bounds b, Transform cap, Transform key, float yaw, float pitch, int flip, string dir, string name)
        {
            if (flip < 0) yaw = -yaw;
            var rot = Quaternion.Euler(pitch, 180f - yaw, 0f); // looks toward -Z at yaw 0
            Vector3 right = Quaternion.Euler(0f, 180f - yaw, 0f) * Vector3.right;
            float reach = b.extents.x * Mathf.Abs(right.x) + b.extents.z * Mathf.Abs(right.z);
            Vector3 c = b.center + right * (reach + 0.5f);
            cap.position = new Vector3(c.x, CapsuleHeight / 2f, c.z);
            var all = b;
            all.Encapsulate(new Bounds(cap.position, new Vector3(0.5f, CapsuleHeight, 0.5f)));
            float r = all.extents.magnitude;
            float dist = r / Mathf.Sin(cam.fieldOfView * 0.5f * Mathf.Deg2Rad) * 1.05f;
            cam.transform.rotation = rot;
            cam.transform.position = all.center - rot * Vector3.forward * dist;

            key.rotation = rot * Quaternion.Euler(35f, 30f, 0f); // key light from the camera's upper left
            var rt = new RenderTexture(Size, Size, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            var prev = RenderTexture.active;
            cam.targetTexture = rt;
            cam.Render();
            RenderTexture.active = rt;
            var tex = new Texture2D(Size, Size, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, Size, Size), 0, 0);
            tex.Apply();
            cam.targetTexture = null;
            RenderTexture.active = prev;
            string path = Path.Combine(dir, name + ".png");
            File.WriteAllBytes(path, tex.EncodeToPNG());
            UnityEngine.Object.DestroyImmediate(tex);
            rt.Release();
            return path.Replace('\\', '/');
        }
    }
}
