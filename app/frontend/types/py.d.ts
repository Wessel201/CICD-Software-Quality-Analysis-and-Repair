// Allow importing .py files as raw strings via webpack asset/source
declare module "*.py" {
  const content: string;
  export default content;
}
