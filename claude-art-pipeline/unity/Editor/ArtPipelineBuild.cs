using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;

namespace AjArtPipeline
{
    /// <summary>Prefab and AnimatorController generator. Re-running overwrites; never hand-wire.</summary>
    public static class ArtPipelineBuild
    {
        public const string PrefabDir = "Assets/Art/Prefabs";

        public static AnimationClip Clip(string modelPath, string name) =>
            AssetDatabase.LoadAllAssetsAtPath(modelPath).OfType<AnimationClip>()
                .FirstOrDefault(c => c.name == name && !c.name.StartsWith("__preview__"));

        public static string MakePrefab(string modelPath)
        {
            var sc = ArtSidecar.Load(modelPath);
            var model = AssetDatabase.LoadAssetAtPath<GameObject>(modelPath);
            if (model == null) throw new System.Exception($"cannot load model {modelPath}");
            string name = Path.GetFileNameWithoutExtension(modelPath);
            Directory.CreateDirectory(PrefabDir);
            var inst = (GameObject)PrefabUtility.InstantiatePrefab(model);
            try
            {
                if (sc != null && sc.rig == "humanoid")
                {
                    var idle = Clip(modelPath, "idle");
                    var walk = Clip(modelPath, "walk");
                    if (idle == null || walk == null)
                        throw new System.Exception($"{modelPath}: humanoid needs clips 'idle' and 'walk' (found idle={idle != null}, walk={walk != null})");
                    var anim = inst.GetComponent<Animator>() ?? inst.AddComponent<Animator>();
                    anim.runtimeAnimatorController = MakeController(name, idle, walk);
                }
                string path = $"{PrefabDir}/{name}.prefab";
                PrefabUtility.SaveAsPrefabAsset(inst, path);
                return path;
            }
            finally { Object.DestroyImmediate(inst); }
        }

        static AnimatorController MakeController(string name, AnimationClip idle, AnimationClip walk)
        {
            string path = $"{PrefabDir}/{name}.controller";
            AssetDatabase.DeleteAsset(path);
            var ctrl = AnimatorController.CreateAnimatorControllerAtPath(path);
            ctrl.AddParameter("Speed", AnimatorControllerParameterType.Float);
            var tree = new BlendTree { name = "Locomotion", blendParameter = "Speed" };
            AssetDatabase.AddObjectToAsset(tree, ctrl);
            tree.AddChild(idle, 0f);
            tree.AddChild(walk, 1f);
            var state = ctrl.layers[0].stateMachine.AddState("Locomotion");
            state.motion = tree;
            ctrl.layers[0].stateMachine.defaultState = state;
            EditorUtility.SetDirty(ctrl);
            AssetDatabase.SaveAssets();
            return ctrl;
        }

        /// <summary>Batch entry: -executeMethod AjArtPipeline.ArtPipelineBuild.MakePrefabBatch -artModel Assets/..fbx</summary>
        public static void MakePrefabBatch()
        {
            try
            {
                var a = System.Environment.GetCommandLineArgs();
                int i = System.Array.IndexOf(a, "-artModel");
                Debug.Log($"[ArtPipeline] prefab: {MakePrefab(a[i + 1])}");
                EditorApplication.Exit(0);
            }
            catch (System.Exception e) { Debug.LogError($"[ArtPipeline] ERROR: {e.Message}"); EditorApplication.Exit(1); }
        }

        [MenuItem("Tools/Art Pipeline/Make Prefab From Selected Model")]
        static void MenuMakePrefab()
        {
            foreach (var o in Selection.objects)
                Debug.Log($"[ArtPipeline] prefab: {MakePrefab(AssetDatabase.GetAssetPath(o))}");
        }
    }
}
