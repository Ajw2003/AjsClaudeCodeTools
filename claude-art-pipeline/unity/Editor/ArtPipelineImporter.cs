using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace AjArtPipeline
{
    /// <summary>Contents of <c>&lt;Model&gt;.art.json</c>, written next to the FBX by the forge.</summary>
    [Serializable]
    public class ArtSidecar
    {
        [Serializable]
        public class Clip { public string name; public bool loop = true; }

        public string kind = "prop";          // prop | character
        public string rig = "none";           // humanoid | generic | none
        public Clip[] clips = new Clip[0];
        public float emission_strength = 1f;  // 8-bit emission clamps at 1; scale back up here

        public static string PathFor(string modelPath) => Path.ChangeExtension(modelPath, null) + ".art.json";

        public static ArtSidecar Load(string modelPath)
        {
            string p = PathFor(modelPath);
            return File.Exists(p) ? JsonUtility.FromJson<ArtSidecar>(File.ReadAllText(p)) : null;
        }
    }

    /// <summary>
    /// Owns import settings for models under <see cref="Root"/> that have a sidecar: rig, avatar, clip
    /// names and loop flags, URP Lit materials from the baked maps, linear data textures.
    /// </summary>
    public class ArtPipelineImporter : AssetPostprocessor
    {
        public const string RootPref = "AjArtPipeline.Root";
        public const string LitShaderName = "Universal Render Pipeline/Lit";
        static readonly string[] LinearSuffixes = { "_ORM", "_MetallicGloss", "_Metallic", "_Roughness" };

        public static string Root
        {
            get
            {
                string r = EditorPrefs.GetString(RootPref, "Assets/Art/Generated/");
                return r.EndsWith("/") ? r : r + "/";
            }
        }

        public override uint GetVersion() => 1;

        static bool InRoot(string path) => path.StartsWith(Root, StringComparison.OrdinalIgnoreCase);

        static ArtSidecar SidecarFor(string path) =>
            path.EndsWith(".fbx", StringComparison.OrdinalIgnoreCase) && InRoot(path) ? ArtSidecar.Load(path) : null;

        public static readonly (string unity, string bone)[] HumanBones =
        {
            ("Hips", "Hips"), ("Spine", "Spine"), ("Chest", "Chest"), ("Neck", "Neck"), ("Head", "Head"),
            ("LeftShoulder", "Shoulder.L"), ("LeftUpperArm", "UpperArm.L"), ("LeftLowerArm", "LowerArm.L"), ("LeftHand", "Hand.L"),
            ("RightShoulder", "Shoulder.R"), ("RightUpperArm", "UpperArm.R"), ("RightLowerArm", "LowerArm.R"), ("RightHand", "Hand.R"),
            ("LeftUpperLeg", "UpperLeg.L"), ("LeftLowerLeg", "LowerLeg.L"), ("LeftFoot", "Foot.L"),
            ("RightUpperLeg", "UpperLeg.R"), ("RightLowerLeg", "LowerLeg.R"), ("RightFoot", "Foot.R"),
        };

        void OnPreprocessModel()
        {
            var sc = SidecarFor(assetPath);
            if (sc == null) return;
            context?.DependsOnSourceAsset(ArtSidecar.PathFor(assetPath));
            var imp = (ModelImporter)assetImporter;
            imp.globalScale = 1f;
            imp.useFileScale = true;
            imp.isReadable = false;
            imp.materialImportMode = ModelImporterMaterialImportMode.ImportViaMaterialDescription;
            switch (sc.rig)
            {
                case "humanoid":
                    imp.animationType = ModelImporterAnimationType.Human;
                    imp.avatarSetup = ModelImporterAvatarSetup.CreateFromThisModel;
                    imp.humanDescription = Describe(imp.humanDescription);
                    break;
                case "generic":
                    imp.animationType = ModelImporterAnimationType.Generic;
                    imp.avatarSetup = ModelImporterAvatarSetup.CreateFromThisModel;
                    break;
                default:
                    imp.animationType = ModelImporterAnimationType.None;
                    imp.importAnimation = false;
                    break;
            }
        }

        static HumanDescription Describe(HumanDescription d)
        {
            if (d.human == null || d.human.Length == 0)   // keep a map already filtered to the bones present
            d.human = HumanBones.Select(b =>
            {
                var hb = new HumanBone { humanName = b.unity, boneName = b.bone };
                hb.limit.useDefaultValues = true;
                return hb;
            }).ToArray();
            d.upperArmTwist = d.lowerArmTwist = d.upperLegTwist = d.lowerLegTwist = 0.5f;
            d.armStretch = d.legStretch = 0.05f;
            d.feetSpacing = 0f;
            d.hasTranslationDoF = false;
            return d;
        }

        // A Humanoid avatar needs the rest pose recorded; do it once, then reimport once.
        void OnPostprocessModel(GameObject root)
        {
            var sc = SidecarFor(assetPath);
            if (sc == null || sc.rig != "humanoid") return;
            var imp = (ModelImporter)assetImporter;
            var d = imp.humanDescription;
            // Shoulders (and any other bone a model lacks) are optional in Unity: map only what exists.
            var names = new HashSet<string>(root.GetComponentsInChildren<Transform>(true).Select(t => t.name));
            var human = HumanBones.Where(b => names.Contains(b.bone)).Select(b =>
            {
                var hb = new HumanBone { humanName = b.unity, boneName = b.bone };
                hb.limit.useDefaultValues = true;
                return hb;
            }).ToArray();
            if (d.skeleton != null && d.skeleton.Length > 0 && d.human != null && d.human.Length == human.Length) return;
            d.human = human;
            d.skeleton = root.GetComponentsInChildren<Transform>(true).Select(t => new SkeletonBone
            {
                name = t.name, position = t.localPosition, rotation = t.localRotation, scale = t.localScale
            }).ToArray();
            imp.humanDescription = Describe(d);
            string path = assetPath;
            Debug.Log($"[ArtPipeline] {path}: recorded rest pose; reimporting once.");
            EditorApplication.delayCall += () => (AssetImporter.GetAtPath(path) as ModelImporter)?.SaveAndReimport();
        }

        void OnPreprocessAnimation()
        {
            var sc = SidecarFor(assetPath);
            if (sc == null || sc.rig == "none") return;
            var imp = (ModelImporter)assetImporter;
            var clips = imp.defaultClipAnimations;
            foreach (var c in clips)
            {
                string raw = c.name.Contains("|") ? c.name.Substring(c.name.LastIndexOf('|') + 1) : c.name;
                var m = sc.clips.FirstOrDefault(x => string.Equals(x.name, raw, StringComparison.OrdinalIgnoreCase));
                if (m == null) continue;
                c.name = m.name;
                c.loopTime = m.loop;
                c.loopPose = m.loop;
            }
            imp.clipAnimations = clips;
        }

        void OnPostprocessMaterial(Material material)
        {
            var sc = SidecarFor(assetPath);
            if (sc == null) return;
            var lit = Shader.Find(LitShaderName);
            if (lit == null)
            {
                Debug.LogError($"[ArtPipeline] {assetPath}: shader '{LitShaderName}' not found (is URP installed?)");
                return;
            }
            string dir = Path.GetDirectoryName(assetPath).Replace('\\', '/');
            string name = Path.GetFileNameWithoutExtension(assetPath);
            material.shader = lit;
            material.SetColor("_BaseColor", Color.white);

            var baseMap = Tex(dir, name, "BaseMap");
            if (baseMap != null) material.SetTexture("_BaseMap", baseMap);
            // URP Lit: metallic = RGB, smoothness = alpha of _MetallicGlossMap.
            var mg = Tex(dir, name, "MetallicGloss");
            if (mg != null)
            {
                material.SetTexture("_MetallicGlossMap", mg);
                material.SetFloat("_Smoothness", 1f);
                material.SetFloat("_SmoothnessTextureChannel", 0f);
                material.EnableKeyword("_METALLICSPECGLOSSMAP");
            }
            var normal = Tex(dir, name, "Normal");
            if (normal != null)
            {
                material.SetTexture("_BumpMap", normal);
                material.EnableKeyword("_NORMALMAP");
            }
            var em = Tex(dir, name, "Emission");
            if (em != null)
            {
                material.SetTexture("_EmissionMap", em);
                material.SetColor("_EmissionColor", Color.white * sc.emission_strength);
                material.EnableKeyword("_EMISSION");
            }
            if (baseMap == null)
                Debug.LogWarning($"[ArtPipeline] {assetPath}: no <Name>_BaseMap.png beside the model or in Textures/; material '{material.name}' is untextured.");
        }

        Texture2D Tex(string dir, string name, string kind)
        {
            foreach (string p in new[] { $"{dir}/Textures/{name}_{kind}.png", $"{dir}/{name}_{kind}.png" })
            {
                var t = AssetDatabase.LoadAssetAtPath<Texture2D>(p);
                if (t != null) { context?.DependsOnArtifact(p); return t; }
            }
            return null;
        }

        void OnPreprocessTexture()
        {
            if (!InRoot(assetPath)) return;
            var imp = (TextureImporter)assetImporter;
            string n = Path.GetFileNameWithoutExtension(assetPath);
            bool normal = n.EndsWith("_Normal", StringComparison.Ordinal);
            if (normal) imp.textureType = TextureImporterType.NormalMap;
            imp.sRGBTexture = !normal && !LinearSuffixes.Any(s => n.EndsWith(s, StringComparison.Ordinal));
        }
    }
}
