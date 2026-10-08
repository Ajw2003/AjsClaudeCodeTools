using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace AjArtPipeline
{
    public static class ArtPipelineSetup
    {
        const string Dir = "Assets/Art/Settings";

        /// <summary>Creates a URP asset + renderer if none; assigns it to Graphics and every Quality level that has none.</summary>
        [MenuItem("Tools/Art Pipeline/Ensure URP")]
        public static void EnsureURP()
        {
            var asset = GraphicsSettings.defaultRenderPipeline as UniversalRenderPipelineAsset;
            if (asset == null)
            {
                string path = $"{Dir}/ArtPipeline_URP.asset";
                asset = AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(path);
                if (asset == null)
                {
                    Directory.CreateDirectory(Dir);
                    var data = ScriptableObject.CreateInstance<UniversalRendererData>();
                    AssetDatabase.CreateAsset(data, $"{Dir}/ArtPipeline_URP_Renderer.asset");
                    asset = UniversalRenderPipelineAsset.Create(data);
                    AssetDatabase.CreateAsset(asset, path);
                }
                GraphicsSettings.defaultRenderPipeline = asset;
            }
            int current = QualitySettings.GetQualityLevel();
            for (int i = 0; i < QualitySettings.names.Length; i++)
            {
                QualitySettings.SetQualityLevel(i, false);
                if (QualitySettings.renderPipeline == null) QualitySettings.renderPipeline = asset;
            }
            QualitySettings.SetQualityLevel(current, false);
            AssetDatabase.SaveAssets();
            Debug.Log($"[ArtPipeline] URP active: {GraphicsSettings.currentRenderPipeline?.name}");
        }
    }
}
